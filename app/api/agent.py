"""Endpoints used only by the voice agent (service-token auth)."""

from __future__ import annotations

import statistics
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.jobs.queue import enqueue
from app.models import BusinessConfig, Call, TranscriptTurn
from app.schemas import CallEndIn, CallStartIn, CallStartOut, ToolCallIn
from app.security import require_agent
from app.services.calendar import get_calendar
from app.services.prompt import build_instructions, greeting_text
from app.services.timeutil import utcnow
from app.services.tools import ToolContext, ToolResult, run_tool

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(require_agent)])

MAX_CONCURRENT_CALLS = 5  # LiveKit Build plan limit; Gemini free tier is similar


def calls_today(db: Session) -> int:
    start = utcnow() - timedelta(hours=24)
    return db.scalar(select(func.count(Call.id)).where(Call.started_at >= start)) or 0


def active_calls(db: Session, settings: Settings) -> int:
    since = utcnow() - timedelta(minutes=settings.effective_max_call_minutes + 2)
    return (
        db.scalar(
            select(func.count(Call.id)).where(Call.status == "active", Call.started_at >= since)
        )
        or 0
    )


def capacity_problem(db: Session, settings: Settings) -> str:
    if settings.demo_mode and calls_today(db) >= settings.demo_daily_calls:
        return "daily_demo_cap"
    if active_calls(db, settings) >= MAX_CONCURRENT_CALLS:
        return "busy"
    return ""


@router.post("/calls/start", response_model=CallStartOut)
def start_call(
    body: CallStartIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> CallStartOut:
    problem = capacity_problem(db, settings)
    if problem:
        return CallStartOut(allowed=False, reason=problem)
    biz = db.get(BusinessConfig, 1)
    if biz is None:
        raise HTTPException(503, "Business is not configured; run the seed")
    now = utcnow()
    call = Call(
        channel=body.channel,
        room_name=body.room_name,
        caller_number=body.caller_number,
        started_at=now,
        status="active",
    )
    db.add(call)
    db.commit()
    minutes = settings.effective_max_call_minutes
    return CallStartOut(
        allowed=True,
        call_id=call.id,
        max_call_seconds=minutes * 60,
        greeting=greeting_text(biz),
        instructions=build_instructions(db, now, minutes),
        voice=biz.voice or settings.voice_name,
        language=biz.language,
        transfer_enabled=settings.transfer_enabled
        and bool(biz.handoff_number or settings.handoff_number),
    )


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return int(statistics.quantiles(values, n=100, method="inclusive")[int(pct) - 1])


@router.post("/calls/{call_id}/end")
def end_call(call_id: uuid.UUID, body: CallEndIn, db: Session = Depends(get_db)) -> dict[str, str]:
    call = db.get(Call, call_id)
    if call is None:
        raise HTTPException(404, "Unknown call")
    if call.status != "active":
        return {"status": call.status}  # idempotent: already ended
    call.ended_at = body.ended_at
    call.duration_s = max(0, int((body.ended_at - call.started_at).total_seconds()))
    call.end_reason = body.end_reason
    call.latency_p50_ms = _percentile(body.latency_ms, 50)
    call.latency_p95_ms = _percentile(body.latency_ms, 95)
    call.interruptions = body.interruptions
    call.audio_input_tokens = body.audio_input_tokens
    call.audio_output_tokens = body.audio_output_tokens
    call.text_tokens = body.text_tokens
    # Gemini Live paid-tier list prices (USD / 1M tokens): audio in 3.00, audio out 12.00.
    call.est_cost_usd = round(
        (body.audio_input_tokens * 3.0 + body.audio_output_tokens * 12.0 + body.text_tokens * 0.5)
        / 1_000_000,
        5,
    )
    call.status = "ended"
    for t in body.turns:
        if t.text.strip():
            db.add(TranscriptTurn(call_id=call.id, speaker=t.speaker, text=t.text.strip(), ts=t.ts))
    enqueue(db, "post_call", {"call_id": str(call.id)}, idempotency_key=f"post_call:{call.id}")
    db.commit()
    return {"status": "ended"}


@router.post("/tools/{tool}", response_model=ToolResult)
def call_tool(
    tool: str,
    body: ToolCallIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ToolResult:
    call = db.get(Call, body.call_id) if body.call_id else None
    ctx = ToolContext(db, get_calendar(settings), settings, call)
    return run_tool(ctx, tool, body.args)
