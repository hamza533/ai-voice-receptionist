"""Twilio webhook for text replies. Twilio signs every request; unsigned ones are refused."""

from __future__ import annotations

from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.db import get_db
from app.services.calendar import get_calendar
from app.services.sms import record_inbound, signature_valid, twiml
from app.services.sms_replies import handle_reply
from app.services.timeutil import utcnow

router = APIRouter(prefix="/api/sms", tags=["sms"])


@router.post("/inbound")
async def inbound(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    if not settings.sms_enabled:
        raise HTTPException(404, "SMS is not configured")
    params = dict(parse_qsl((await request.body()).decode(), keep_blank_values=True))
    # Twilio signs the public URL it called, which is the web app's address (the request
    # reaches the API through the web app's /api rewrite).
    url = settings.public_url.rstrip("/") + "/api/sms/inbound"
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature_valid(url, params, signature, settings.twilio_auth_token):
        raise HTTPException(403, "Invalid signature")
    phone, text = params.get("From", ""), params.get("Body", "")

    def _run() -> str:
        record_inbound(db, phone, text, params.get("MessageSid", ""))
        return handle_reply(
            db, get_calendar(settings), settings, phone=phone, text=text, now=utcnow()
        )

    reply = await run_in_threadpool(_run)
    return Response(twiml(reply), media_type="application/xml")
