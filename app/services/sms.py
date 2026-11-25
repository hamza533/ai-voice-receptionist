"""Text messages to customers: an idempotent outbox in front of Twilio.

Like the email outbox, every text has an idempotency key, so a retried job never sends the
same message twice. Without Twilio credentials texts are recorded as "skipped": the
dashboard still shows what would have been sent, and nothing else changes.

Replies come back through Twilio's webhook (`/api/sms/inbound`), which is only accepted
with a valid `X-Twilio-Signature`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from html import escape

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import SmsMessage
from app.services.privacy import normalize_phone
from app.services.timeutil import utcnow

log = logging.getLogger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01"
# Tests swap in an httpx.MockTransport so no real text is ever sent.
DEFAULT_TRANSPORT: httpx.BaseTransport | None = None


class SmsError(Exception):
    pass


def to_e164(phone: str, default_country_code: str = "") -> str:
    """Best-effort E.164: keep +numbers, prefix local numbers with the default country code.
    Returns "" when the number can't be made international (the text is then skipped)."""
    p = normalize_phone(phone)
    if not p:
        return ""
    if p.startswith("+"):
        return p
    if p.startswith("00"):
        return "+" + p[2:]
    if default_country_code:
        code = "+" + default_country_code.lstrip("+")
        return code + p.lstrip("0")
    return ""


def send_sms(
    db: Session,
    settings: Settings,
    *,
    key: str,
    to: str,
    body: str,
    kind: str,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Send once per key. Returns the final status: sent | skipped. Raises SmsError on a
    provider failure so the job is retried."""
    row = db.scalar(select(SmsMessage).where(SmsMessage.idempotency_key == key))
    if row is not None and row.status in {"sent", "skipped"}:
        return row.status
    number = to_e164(to, settings.sms_default_country_code)
    if row is None:
        row = SmsMessage(
            direction="out", idempotency_key=key, phone=number or to, body=body, kind=kind
        )
        db.add(row)
        db.commit()

    if not settings.sms_enabled or not number:
        row.status = "skipped"
        row.error = "sms not configured" if number else "no international number"
        db.commit()
        log.info("sms skipped", extra={"kind": kind, "reason": row.error})
        return "skipped"

    sid = settings.twilio_account_sid
    with httpx.Client(timeout=15, transport=transport or DEFAULT_TRANSPORT) as client:
        resp = client.post(
            f"{TWILIO_API}/Accounts/{sid}/Messages.json",
            data={"To": number, "From": settings.twilio_from_number, "Body": body},
            auth=(sid, settings.twilio_auth_token),
        )
    if resp.status_code >= 300:
        row.error = f"twilio {resp.status_code}: {resp.text[:300]}"
        db.commit()
        raise SmsError(row.error)
    row.status = "sent"
    row.provider_id = str(resp.json().get("sid", ""))[:64]
    row.sent_at = utcnow()
    row.error = None
    db.commit()
    log.info("sms sent", extra={"kind": kind, "sms_id": row.id})
    return "sent"


def record_inbound(db: Session, phone: str, body: str, provider_id: str) -> SmsMessage:
    row = SmsMessage(
        direction="in",
        phone=normalize_phone(phone),
        body=body[:1600],
        kind="reply",
        status="received",
        provider_id=provider_id[:64] or None,
    )
    db.add(row)
    db.commit()
    return row


def twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    """Twilio's request signature: HMAC-SHA1 of the URL followed by each POST parameter
    (sorted by name, name+value), base64-encoded."""
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def signature_valid(url: str, params: dict[str, str], signature: str, auth_token: str) -> bool:
    if not auth_token or not signature:
        return False
    return hmac.compare_digest(twilio_signature(url, params, auth_token), signature)


def twiml(message: str) -> str:
    """A TwiML reply that texts `message` back to the sender."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(message)}</Message></Response>"
    )
