"""Settings → Integrations: connect Google Calendar with a button, and status of SMS."""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Integration, User
from app.security import current_user, require_admin
from app.services import google_oauth
from app.services.calendar import connected_calendar, get_calendar, invalidate_connection_cache
from app.services.crypto import decrypt, encrypt

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["integrations"])

STATE_COOKIE = "g_oauth_state"
PROVIDER = "google_calendar"


class CalendarPick(BaseModel):
    calendar_id: str = Field(min_length=1, max_length=255)


def _row(db: Session) -> Integration | None:
    return db.scalar(select(Integration).where(Integration.provider == PROVIDER))


@router.get("")
def status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(current_user),
) -> dict[str, object]:
    row = _row(db)
    calendar = get_calendar(settings)
    if row and row.calendar_id and calendar.name == "google":
        mode = "connected"
    elif settings.calendar_enabled:
        mode = "service_account"
    else:
        mode = "built_in"
    return {
        "google": {
            "available": settings.google_oauth_enabled,
            "connected": row is not None,
            "account_email": row.account_email if row else "",
            "calendar_id": row.calendar_id if row else "",
            "mode": mode,
        },
        "sms": {"configured": settings.sms_enabled, "from_number": settings.twilio_from_number},
    }


@router.get("/google/start")
def google_start(
    settings: Settings = Depends(get_settings), _: User = Depends(require_admin)
) -> RedirectResponse:
    if not settings.google_oauth_enabled:
        raise HTTPException(503, "Google sign-in is not set up (GOOGLE_OAUTH_CLIENT_ID missing)")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(google_oauth.auth_url(settings, state), status_code=302)
    resp.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/integrations/google",
    )
    return resp


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(require_admin),
) -> RedirectResponse:
    def done(result: str) -> RedirectResponse:
        resp = RedirectResponse(f"/dashboard/settings?calendar={result}", status_code=302)
        resp.delete_cookie(STATE_COOKIE, path="/api/integrations/google")
        return resp

    expected = request.cookies.get(STATE_COOKIE, "")
    if error or not code or not expected or not secrets.compare_digest(state, expected):
        return done("cancelled" if error else "error")
    try:
        tokens = google_oauth.exchange_code(settings, code)
    except Exception:  # OAuthError or network: the owner just tries again
        log.exception("google oauth token exchange failed")
        return done("error")
    row = _row(db) or Integration(provider=PROVIDER, calendar_id="")
    row.refresh_token_enc = encrypt(settings, tokens["refresh_token"])
    row.account_email = google_oauth.account_email(tokens.get("access_token", ""))
    if not row.calendar_id and row.account_email:
        row.calendar_id = row.account_email  # the account's primary calendar
    db.add(row)
    db.commit()
    invalidate_connection_cache()
    return done("connected")


@router.get("/google/calendars")
def google_calendars(
    settings: Settings = Depends(get_settings), _: User = Depends(require_admin)
) -> list[dict[str, object]]:
    client = connected_calendar(settings)
    if client is None:
        raise HTTPException(404, "Google Calendar is not connected")
    try:
        return client.list_calendars()
    except Exception as exc:
        log.exception("listing calendars failed")
        raise HTTPException(502, "Couldn't reach Google Calendar. Try connecting again.") from exc


@router.put("/google")
def google_pick_calendar(
    body: CalendarPick,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict[str, str]:
    row = _row(db)
    if row is None:
        raise HTTPException(404, "Google Calendar is not connected")
    row.calendar_id = body.calendar_id
    db.commit()
    invalidate_connection_cache()
    return {"calendar_id": row.calendar_id}


@router.delete("/google", status_code=204)
def google_disconnect(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(require_admin),
) -> None:
    row = _row(db)
    if row is None:
        return
    token = decrypt(settings, row.refresh_token_enc)
    if token:
        google_oauth.revoke(token)
    db.delete(row)
    db.commit()
    invalidate_connection_cache()
