"""SMTP email with an idempotent outbox.

Each email has an idempotency key. The outbox row is checked before sending, so a
retried job never sends the same email twice once it has been marked sent. The
Message-ID is derived from the key too, so mail clients de-duplicate the rare resend.
"""

from __future__ import annotations

import hashlib
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import EmailOutbox
from app.services.timeutil import utcnow

log = logging.getLogger(__name__)


def _message_id(key: str, sender: str) -> str:
    domain = sender.rsplit("@", 1)[-1].strip(">") if "@" in sender else "localhost"
    return f"<{hashlib.sha256(key.encode()).hexdigest()[:32]}@{domain}>"


def send_email(
    db: Session,
    settings: Settings,
    *,
    key: str,
    to: str,
    subject: str,
    body: str,
    kind: str,
) -> str:
    """Send once per key. Returns the final status: sent | skipped."""
    row = db.scalar(select(EmailOutbox).where(EmailOutbox.idempotency_key == key))
    if row is not None and row.status in {"sent", "skipped"}:
        return row.status
    if row is None:
        row = EmailOutbox(idempotency_key=key, to_address=to, subject=subject, body=body, kind=kind)
        db.add(row)
        db.commit()

    if not settings.smtp_enabled or not to:
        row.status = "skipped"
        row.error = "smtp not configured" if to else "no recipient"
        db.commit()
        log.info("email skipped", extra={"kind": kind, "reason": row.error})
        return "skipped"

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = _message_id(key, settings.email_from)
    msg.set_content(body)

    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=15,
            context=ssl.create_default_context(),
        ) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)

    row.status = "sent"
    row.sent_at = utcnow()
    row.error = None
    db.commit()
    log.info("email sent", extra={"kind": kind, "outbox_id": row.id})
    return "sent"
