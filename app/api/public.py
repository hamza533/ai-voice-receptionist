"""Public endpoints: health, landing-page info, web-call tokens, FAQ test."""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.agent import capacity_problem
from app.config import Settings, get_settings
from app.db import get_db
from app.models import BusinessConfig, OpeningHours, Service, Staff
from app.schemas import WebCallTokenOut
from app.security import client_ip, hit_rate_limit
from app.services.calendar import get_calendar
from app.services.timeutil import WEEKDAYS
from app.services.tools import FaqIn, ToolContext, answer_faq

router = APIRouter(tags=["public"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict:
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    checks["business_config"] = "ok" if db.get(BusinessConfig, 1) else "missing (run seed)"
    checks["calendar"] = get_calendar(settings).name
    checks["livekit"] = "configured" if settings.livekit_enabled else "not configured"
    checks["llm"] = "configured" if settings.gemini_api_key else "not configured"
    checks["smtp"] = "configured" if settings.smtp_enabled else "not configured"
    if checks["database"] != "ok":
        raise HTTPException(503, detail=checks)
    return {"status": "ready", "checks": checks, "demo_mode": settings.demo_mode}


@router.get("/api/public/business")
def public_business(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    biz = db.get(BusinessConfig, 1)
    if biz is None:
        raise HTTPException(404, "Not configured")
    hours: dict[str, list[str]] = {d.title(): [] for d in WEEKDAYS}
    for h in db.scalars(
        select(OpeningHours).order_by(OpeningHours.weekday, OpeningHours.open_time)
    ):
        hours[WEEKDAYS[h.weekday].title()].append(f"{h.open_time:%H:%M}–{h.close_time:%H:%M}")
    return {
        "name": biz.name,
        "address": biz.address,
        "phone": biz.phone,
        "currency": biz.currency,
        "timezone": biz.timezone,
        "greeting": biz.greeting,
        "hours": hours,
        "services": [
            {"name": s.name, "duration_min": s.duration_min, "price": float(s.price)}
            for s in db.scalars(
                select(Service).where(Service.active.is_(True)).order_by(Service.id)
            )
        ],
        "staff": [
            {"name": s.name, "title": s.title}
            for s in db.scalars(select(Staff).where(Staff.active.is_(True)).order_by(Staff.id))
        ],
        "demo_mode": settings.demo_mode,
        "max_call_minutes": settings.effective_max_call_minutes,
        "web_call_enabled": settings.livekit_enabled,
    }


@router.post("/api/web-call/token", response_model=WebCallTokenOut)
def web_call_token(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebCallTokenOut:
    """Short-lived token limited to one new room; the agent is dispatched into it."""
    if hit_rate_limit(
        db,
        f"webcall:{client_ip(request)}",
        limit=settings.demo_rate_limit_per_minute if settings.demo_mode else 30,
        window=timedelta(minutes=1),
    ):
        raise HTTPException(429, "Too many calls from your network. Try again in a minute.")
    if not settings.livekit_enabled:
        raise HTTPException(503, "Web calls are not configured (LIVEKIT_* missing)")
    problem = capacity_problem(db, settings)
    if problem:
        raise HTTPException(
            503,
            "Receptionist is busy, try again in a minute"
            if problem == "busy"
            else "Today's demo call limit is reached. Try again tomorrow.",
        )

    from livekit import api as lk

    room = f"web-{secrets.token_hex(6)}"
    identity = f"caller-{secrets.token_hex(4)}"
    ttl = settings.web_call_token_ttl_s
    token = (
        lk.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name("Web caller")
        .with_ttl(timedelta(seconds=ttl))
        .with_grants(
            lk.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                room_create=False,
                room_admin=False,
                room_list=False,
            )
        )
        .with_room_config(
            lk.RoomConfiguration(
                agents=[lk.RoomAgentDispatch(agent_name=settings.livekit_agent_name)],
                empty_timeout=60,
                max_participants=3,
            )
        )
        .to_jwt()
    )
    return WebCallTokenOut(
        token=token, url=settings.livekit_url, room=room, identity=identity, expires_in=ttl
    )


class FaqTestIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)


@router.post("/api/public/faq-test")
def faq_test(
    body: FaqTestIn,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Used by the Knowledge page's 'Test Ava's knowledge' box and the landing page."""
    if hit_rate_limit(db, f"faqtest:{client_ip(request)}", limit=30, window=timedelta(minutes=1)):
        raise HTTPException(429, "Slow down a little")
    ctx = ToolContext(db, get_calendar(settings), settings, call=None)
    res = answer_faq(ctx, FaqIn(question=body.question))
    return res.model_dump()
