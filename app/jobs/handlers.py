"""Job handlers. Each one is idempotent: running it twice has the same effect as once."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.llm import LLM, LLMUnavailable, record_usage
from app.models import (
    Appointment,
    BusinessConfig,
    Call,
    EmailOutbox,
    Job,
    Message,
    RateLimit,
    ToolCall,
    TranscriptTurn,
    UserSession,
)
from app.services.calendar import calendar_for_staff, get_calendar
from app.services.email import send_email
from app.services.timeutil import speak_time, utcnow

log = logging.getLogger(__name__)

OUTCOMES = [
    "booked",
    "rescheduled",
    "cancelled",
    "faq_answered",
    "message_taken",
    "handed_to_human",
    "abandoned",
]

# Precedence when several things happened in one call.
_TOOL_OUTCOME = [
    ("request_human", "handed_to_human"),
    ("book_appointment", "booked"),
    ("reschedule_appointment", "rescheduled"),
    ("cancel_appointment", "cancelled"),
    ("take_message", "message_taken"),
    ("answer_faq", "faq_answered"),
    ("get_business_info", "faq_answered"),
    ("check_availability", "faq_answered"),
]


def outcome_from_tools(tool_calls: list[ToolCall], caller_turns: int) -> str:
    ok = {t.tool for t in tool_calls if t.result_status == "ok"}
    for tool, outcome in _TOOL_OUTCOME:
        if tool in ok:
            return outcome
    # No action taken: the summary model may refine this (e.g. a question answered from
    # the instructions); without it the call counts as abandoned.
    return "abandoned"


class CallSummary(BaseModel):
    summary: str = Field(description="2-3 sentence summary for salon staff, no phone/email")
    outcome: Literal["faq_answered", "abandoned"] = Field(
        description="faq_answered if the caller's question was answered, else abandoned"
    )
    sentiment: str = Field(description="positive | neutral | negative")
    follow_up_needed: bool


SUMMARY_SYSTEM = (
    "You summarise phone calls handled by an AI receptionist for a small business. "
    "Write for the business owner. Be factual and brief. Never include phone numbers or "
    "email addresses. Mention the service, date and time if a booking changed."
)


def _fallback_summary(call: Call, outcome: str, tool_calls: list[ToolCall]) -> str:
    parts = {
        "booked": "Caller booked an appointment.",
        "rescheduled": "Caller moved an existing appointment.",
        "cancelled": "Caller cancelled an appointment.",
        "message_taken": "Receptionist took a message for staff.",
        "handed_to_human": "Caller asked for a person; staff were notified.",
        "faq_answered": "Caller asked questions and got answers.",
        "abandoned": "Caller hung up before anything was done.",
    }
    detail = next(
        (
            t.result_summary
            for t in reversed(tool_calls)
            if t.result_status == "ok" and t.result_summary
        ),
        "",
    )
    return f"{parts[outcome]} {detail}".strip()


def handle_post_call(db: Session, settings: Settings, payload: dict[str, Any]) -> None:
    call = db.get(Call, uuid.UUID(payload["call_id"]))
    if call is None or call.status == "processed":
        return
    turns = list(call.turns)
    tool_calls = list(call.tool_calls)
    outcome = outcome_from_tools(tool_calls, sum(1 for t in turns if t.speaker == "caller"))

    summary: str | None = None
    llm = LLM(settings)
    if llm.available and turns:
        transcript = "\n".join(f"{t.speaker.upper()}: {t.text}" for t in turns)[-12000:]
        tools = "\n".join(f"- {t.tool}: {t.result_status} {t.result_summary}" for t in tool_calls)
        prompt = (
            f"Outcome (from system records): {outcome}\nTool calls:\n{tools or '- none'}\n\n"
            f"Transcript:\n{transcript}"
        )
        try:
            res = llm.generate_json(prompt, CallSummary, system=SUMMARY_SYSTEM)
            summary = res.value.summary
            if outcome == "abandoned" and not any(t.result_status == "ok" for t in tool_calls):
                outcome = res.value.outcome
            record_usage(db, res, purpose="call_summary", call_id=call.id)  # type: ignore[arg-type]
            call.text_tokens = (call.text_tokens or 0) + res.input_tokens + res.output_tokens
            call.est_cost_usd = (call.est_cost_usd or 0) + res.cost_usd
        except LLMUnavailable:
            summary = None
        except Exception:
            # Never lose a call record because the LLM is down: use the rule-based summary.
            log.exception(
                "summary generation failed; using fallback", extra={"call_id": str(call.id)}
            )
            summary = None
    call.summary = summary or _fallback_summary(call, outcome, tool_calls)
    call.outcome = outcome
    call.status = "processed"
    db.commit()


def handle_send_booking_email(db: Session, settings: Settings, payload: dict[str, Any]) -> None:
    appt = db.get(Appointment, uuid.UUID(payload["appointment_id"]))
    if appt is None or not appt.email:
        return
    biz = db.get(BusinessConfig, 1)
    name = biz.name if biz else "our salon"
    tz = biz.timezone if biz else "UTC"
    change = payload["change"]
    when = speak_time(appt.start_utc, tz)
    titles = {
        "booked": f"Your appointment at {name} is confirmed",
        "rescheduled": f"Your appointment at {name} has moved",
        "cancelled": f"Your appointment at {name} is cancelled",
    }
    lines = {
        "booked": f"You're booked for {appt.service.name} with {appt.staff.name} on {when}.",
        "rescheduled": f"Your {appt.service.name} with {appt.staff.name} is now on {when}.",
        "cancelled": f"Your {appt.service.name} on {when} has been cancelled.",
    }
    body = (
        f"Hi {appt.customer_name},\n\n{lines[change]}\n\n"
        f"{('Address: ' + biz.address) if biz and biz.address else ''}\n"
        "Need to change it? Just call us and the receptionist will help.\n\n"
        f"{biz.email_signature if biz and biz.email_signature else name}\n"
        f"Ref: {str(appt.id)[:8]}"
    )
    send_email(
        db,
        settings,
        key=f"email:{appt.id}:{change}:{appt.start_utc.isoformat()}",
        to=appt.email,
        subject=titles[change],
        body=body,
        kind=f"customer_{change}",
    )


def handle_send_staff_message(db: Session, settings: Settings, payload: dict[str, Any]) -> None:
    msg = db.get(Message, int(payload["message_id"]))
    if msg is None:
        return
    biz = db.get(BusinessConfig, 1)
    to = settings.staff_notify_email or (biz.staff_notify_email if biz else "")
    prefix = "URGENT – caller asked for a person" if msg.urgent else "New message"
    body = (
        f"{prefix}\n\nFrom: {msg.name}\nCall back: {msg.callback_number}\n\n{msg.text}\n\n"
        f"Open the dashboard to mark it handled."
    )
    send_email(
        db,
        settings,
        key=f"email:message:{msg.id}",
        to=to,
        subject=f"[{'URGENT' if msg.urgent else 'Message'}] {msg.name} – callback requested",
        body=body,
        kind="staff_message",
    )


def handle_purge(db: Session, settings: Settings, payload: dict[str, Any]) -> None:
    """Retention purge. See docs/architecture.md → Data retention."""
    now = utcnow()
    cutoff = now - timedelta(days=settings.transcript_retention_days)
    old_calls = select(Call.id).where(Call.started_at < cutoff)
    db.execute(delete(TranscriptTurn).where(TranscriptTurn.call_id.in_(old_calls)))
    db.execute(update(ToolCall).where(ToolCall.call_id.in_(old_calls)).values(args={}))
    db.execute(
        update(Call)
        .where(Call.started_at < cutoff, Call.caller_number != "")
        .values(caller_number="", summary="[purged after retention period]")
    )
    db.execute(
        update(Message)
        .where(Message.created_at < cutoff, Message.handled.is_(True))
        .values(name="[purged]", callback_number="", text="[purged]")
    )
    db.execute(delete(EmailOutbox).where(EmailOutbox.created_at < cutoff))
    year_ago = now - timedelta(days=365)
    db.execute(
        update(Appointment)
        .where(Appointment.end_utc < year_ago, Appointment.customer_name != "[purged]")
        .values(customer_name="[purged]", phone="", email="")
    )
    db.execute(delete(UserSession).where(UserSession.expires_at < now))
    db.execute(delete(RateLimit).where(RateLimit.window_start < now - timedelta(days=2)))
    db.execute(delete(Job).where(Job.status == "done", Job.finished_at < now - timedelta(days=14)))
    db.commit()
    log.info("retention purge done", extra={"cutoff": cutoff.isoformat()})


def handle_demo_reset(db: Session, settings: Settings, payload: dict[str, Any]) -> None:
    """Nightly in demo mode: remove bookings made by demo callers and restore sample data."""
    if not settings.demo_mode:
        return
    from app.seed import seed_demo_activity

    calendar = get_calendar(settings)
    for appt in db.scalars(select(Appointment).where(Appointment.calendar_event_id.is_not(None))):
        if appt.calendar_event_id:
            try:
                calendar.delete_event(
                    calendar_for_staff(appt.staff, settings.google_calendar_id),
                    appt.calendar_event_id,
                )
            except Exception:
                log.exception("demo reset: calendar delete failed")
    db.execute(delete(Appointment))
    db.commit()
    seed_demo_activity(db, settings, reset=True)
    log.info("demo calendar reset done")


HANDLERS: dict[str, Callable[[Session, Settings, dict[str, Any]], None]] = {
    "post_call": handle_post_call,
    "send_booking_email": handle_send_booking_email,
    "send_staff_message": handle_send_staff_message,
    "purge": handle_purge,
    "demo_reset": handle_demo_reset,
}
