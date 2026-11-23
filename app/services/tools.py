"""The receptionist's tools. The agent calls these over HTTPS; the eval runner calls them
in-process. Every tool validates its input and returns a structured `ToolResult`.

Guardrails enforced here (not just in the prompt):
- book/reschedule only accept a `slot_id` that check_availability returned in this call,
  so the agent cannot invent a time,
- booking requires `caller_confirmed=true` (details were read back and the caller said yes),
- reschedule/cancel only find bookings whose phone or email matches what the caller gave,
  and they return the booking for read-back first unless `caller_confirmed=true`.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import time as _time
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.jobs.queue import enqueue
from app.models import FAQ, BusinessConfig, Call, Message, OpeningHours, Service, Staff, ToolCall
from app.services import booking as booking_svc
from app.services.availability import find_slots
from app.services.calendar import CalendarClient
from app.services.privacy import normalize_email, normalize_phone, redact
from app.services.timeutil import WEEKDAYS, ResolvedDate, resolve_date, speak_time, utcnow

ToolStatus = Literal[
    "ok", "error", "not_found", "unavailable", "needs_confirmation", "invalid", "transferred"
]


class ToolResult(BaseModel):
    status: ToolStatus
    message: str = Field(description="Short instruction for the agent: what to say or do next")
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- inputs


class _Base(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class BusinessInfoIn(_Base):
    topic: Literal["all", "hours", "address", "services", "staff", "contact"] = "all"


class FaqIn(_Base):
    question: str = Field(min_length=2, max_length=500)


class AvailabilityIn(_Base):
    service: str = Field(min_length=2, max_length=120)
    date_from: str = Field(description="ISO date or phrase like 'tomorrow', 'next friday'")
    date_to: str | None = None
    staff: str | None = None
    time_of_day: Literal["any", "morning", "afternoon", "evening"] = "any"


class BookIn(_Base):
    slot_id: str = Field(pattern=r"^\d+:\d{8}T\d{4}Z$")
    service: str = Field(min_length=2, max_length=120)
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=500)
    caller_confirmed: bool = False


class FindIn(_Base):
    contact: str = Field(min_length=5, max_length=255, description="phone or email used to book")
    date: str = Field(description="date of the existing booking (ISO or phrase)")
    appointment_ref: str | None = Field(default=None, max_length=36)


class RescheduleIn(FindIn):
    new_slot_id: str = Field(pattern=r"^\d+:\d{8}T\d{4}Z$")
    caller_confirmed: bool = False


class CancelIn(FindIn):
    caller_confirmed: bool = False


class MessageIn(_Base):
    name: str = Field(min_length=1, max_length=120)
    callback_number: str = Field(min_length=5, max_length=40)
    message: str = Field(min_length=2, max_length=2000)
    urgent: bool = False

    @field_validator("callback_number")
    @classmethod
    def _phone(cls, v: str) -> str:
        if not normalize_phone(v):
            raise ValueError("callback number must have at least 7 digits")
        return v


class HumanIn(_Base):
    name: str = Field(default="Caller", max_length=120)
    callback_number: str = Field(default="", max_length=40)
    reason: str = Field(default="Caller asked to speak to a person", max_length=1000)


TOOL_INPUTS: dict[str, type[_Base]] = {
    "get_business_info": BusinessInfoIn,
    "answer_faq": FaqIn,
    "check_availability": AvailabilityIn,
    "book_appointment": BookIn,
    "reschedule_appointment": RescheduleIn,
    "cancel_appointment": CancelIn,
    "take_message": MessageIn,
    "request_human": HumanIn,
}


# ---------------------------------------------------------------- context


class ToolContext:
    def __init__(
        self,
        db: Session,
        calendar: CalendarClient,
        settings: Settings,
        call: Call | None,
        now_utc: datetime | None = None,
    ) -> None:
        self.db = db
        self.calendar = calendar
        self.settings = settings
        self.call = call
        self.now = now_utc or utcnow()
        biz = db.get(BusinessConfig, 1)
        if biz is None:
            raise RuntimeError("business config missing: run `make seed`")
        self.biz = biz

    @property
    def tz(self) -> str:
        return self.biz.timezone

    def money(self, amount: object) -> str:
        return f"{self.biz.currency} {float(str(amount)):,.0f}"


def _match_name(name: str, options: list[str]) -> str | None:
    lowered = {o.lower(): o for o in options}
    key = name.strip().lower()
    if key in lowered:
        return lowered[key]
    for low, orig in lowered.items():
        if key in low or low in key:
            return orig
    close = difflib.get_close_matches(key, list(lowered), n=1, cutoff=0.6)
    return lowered[close[0]] if close else None


def _find_service(ctx: ToolContext, name: str) -> Service | None:
    services = list(ctx.db.scalars(select(Service).where(Service.active.is_(True))))
    hit = _match_name(name, [s.name for s in services])
    return next((s for s in services if s.name == hit), None)


def _find_staff(ctx: ToolContext, name: str) -> Staff | None:
    staff = list(ctx.db.scalars(select(Staff).where(Staff.active.is_(True))))
    hit = _match_name(name, [s.name for s in staff])
    return next((s for s in staff if s.name == hit), None)


def _parse_slot(slot_id: str) -> tuple[int, datetime]:
    staff_part, ts = slot_id.split(":", 1)
    start = datetime.strptime(ts, "%Y%m%dT%H%MZ").replace(tzinfo=UTC)
    return int(staff_part), start


def _offered_in_call(ctx: ToolContext, slot_id: str) -> bool:
    if ctx.call is None:
        return False
    rows = ctx.db.scalars(
        select(ToolCall).where(
            ToolCall.call_id == ctx.call.id,
            ToolCall.tool == "check_availability",
            ToolCall.result_status == "ok",
        )
    )
    return any(slot_id in (r.result_data or {}).get("slot_ids", []) for r in rows)


def _resolve(ctx: ToolContext, phrase: str) -> ResolvedDate:
    return resolve_date(phrase, ctx.tz, ctx.now)


_TIME_WINDOWS = {
    "morning": (None, time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), None),
    "any": (None, None),
}


# ---------------------------------------------------------------- tools


def get_business_info(ctx: ToolContext, args: BusinessInfoIn) -> ToolResult:
    db = ctx.db
    hours_rows = sorted(db.scalars(select(OpeningHours)), key=lambda h: (h.weekday, h.open_time))
    hours: dict[str, str] = {}
    for d, day in enumerate(WEEKDAYS):
        spans = [f"{h.open_time:%H:%M}–{h.close_time:%H:%M}" for h in hours_rows if h.weekday == d]
        hours[day.title()] = ", ".join(spans) if spans else "closed"
    services = [
        {
            "name": s.name,
            "duration_min": s.duration_min,
            "price": ctx.money(s.price),
            "description": s.description,
        }
        for s in db.scalars(select(Service).where(Service.active.is_(True)).order_by(Service.id))
    ]
    staff = [
        {"name": s.name, "title": s.title, "services": [x.name for x in s.services]}
        for s in db.scalars(select(Staff).where(Staff.active.is_(True)).order_by(Staff.id))
    ]
    data: dict[str, Any] = {
        "name": ctx.biz.name,
        "timezone": ctx.tz,
        "today": speak_time(ctx.now, ctx.tz).split(" at ")[0],
    }
    if args.topic in {"all", "hours"}:
        data["opening_hours"] = hours
    if args.topic in {"all", "address", "contact"}:
        data["address"] = ctx.biz.address
        data["phone"] = ctx.biz.phone
        data["website"] = ctx.biz.website
    if args.topic in {"all", "services"}:
        data["services"] = services
    if args.topic in {"all", "staff"}:
        data["staff"] = staff
    return ToolResult(status="ok", message="Answer from this data only.", data=data)


_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "do",
    "you",
    "i",
    "is",
    "are",
    "can",
    "to",
    "of",
    "for",
    "my",
    "what",
    "how",
    "your",
    "in",
    "on",
    "it",
    "and",
    "or",
    "be",
    "have",
    "does",
    "there",
    "any",
}


def _stem(word: str) -> str:
    for suffix in ("ing", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


def answer_faq(ctx: ToolContext, args: FaqIn) -> ToolResult:
    """Keyword overlap over question + tags. The FAQ list of a small business is short,
    so this beats a vector database on cost and predictability (see DECISIONS.md)."""
    q = _tokens(args.question)
    best: tuple[float, FAQ | None] = (0.0, None)
    for faq in ctx.db.scalars(select(FAQ).where(FAQ.active.is_(True))):
        f = _tokens(faq.question + " " + faq.tags)
        if not f or not q:
            continue
        score = len(q & f) / len(q | f)
        ratio = difflib.SequenceMatcher(None, args.question.lower(), faq.question.lower()).ratio()
        if ratio > 0.75:  # near-verbatim question
            score = max(score, ratio)
        if score > best[0]:
            best = (score, faq)
    score, match = best
    if match is None or score < 0.2:
        return ToolResult(
            status="not_found",
            message="No FAQ covers this. Say you're not sure and offer to take a message "
            "for the team. Do not guess.",
        )
    return ToolResult(
        status="ok",
        message="Answer using this FAQ entry in your own words.",
        data={"question": match.question, "answer": match.answer, "match": round(score, 2)},
    )


def check_availability(ctx: ToolContext, args: AvailabilityIn) -> ToolResult:
    service = _find_service(ctx, args.service)
    if service is None:
        names = [s.name for s in ctx.db.scalars(select(Service).where(Service.active.is_(True)))]
        return ToolResult(
            status="invalid",
            message="Unknown service. Ask which of these they want.",
            data={"services": names},
        )
    staff_id = None
    if args.staff and args.staff.lower() not in {"anyone", "any", "no preference"}:
        staff = _find_staff(ctx, args.staff)
        if staff is None or staff not in service.staff:
            offering = [s.name for s in service.staff if s.active]
            return ToolResult(
                status="invalid",
                message=f"That person doesn't do {service.name}. Offer: {', '.join(offering)}.",
                data={"staff_for_service": offering},
            )
        staff_id = staff.id
    try:
        start = _resolve(ctx, args.date_from)
        end = _resolve(ctx, args.date_to) if args.date_to else None
    except ValueError as exc:
        return ToolResult(status="invalid", message=str(exc))
    date_to = end.date if end else start.date + timedelta(days=2)
    if date_to < start.date:
        date_to = start.date
    after, before = _TIME_WINDOWS[args.time_of_day]
    slots = find_slots(
        ctx.db,
        ctx.calendar,
        ctx.settings,
        service=service,
        date_from=start.date,
        date_to=date_to,
        staff_id=staff_id,
        now_utc=ctx.now,
        limit=6,
        after_local_time=after,
        before_local_time=before,
    )
    if not slots:
        # Look further ahead so the agent can offer the next opening, not a dead end.
        slots = find_slots(
            ctx.db,
            ctx.calendar,
            ctx.settings,
            service=service,
            date_from=date_to + timedelta(days=1),
            date_to=date_to + timedelta(days=14),
            staff_id=staff_id,
            now_utc=ctx.now,
            limit=3,
            after_local_time=after,
            before_local_time=before,
        )
        if not slots:
            return ToolResult(
                status="unavailable",
                message="Nothing free in that period or the two weeks after. Offer to take a "
                "message so the team can call back.",
                data={"resolved_date": start.as_dict()},
            )
        message = (
            "Nothing free on the requested dates. These are the next openings; offer them. "
            "Only these times may be offered."
        )
    else:
        message = "Offer two or three of these times. Only these times may be offered."
    if start.ambiguous:
        message = (
            f"The date is ambiguous: confirm whether they mean {start.spoken} or "
            f"{start.as_dict()['alternative_spoken']} before offering times. " + message
        )
    return ToolResult(
        status="ok",
        message=message,
        data={
            "service": service.name,
            "duration_min": service.duration_min,
            "price": ctx.money(service.price),
            "resolved_date": start.as_dict(),
            "slots": [s.as_dict(ctx.tz) for s in slots],
            "slot_ids": [s.as_dict(ctx.tz)["slot_id"] for s in slots],
        },
    )


def _readback(
    ctx: ToolContext, service: str, staff: str, start: datetime, name: str, contact: str
) -> str:
    return (
        f"{service} with {staff} on {speak_time(start, ctx.tz)} for {name}, "
        f"confirmation to {contact or 'no email'}"
    )


def book_appointment(ctx: ToolContext, args: BookIn) -> ToolResult:
    if not _offered_in_call(ctx, args.slot_id):
        return ToolResult(
            status="invalid",
            message="That slot was not offered by check_availability in this call. Check "
            "availability first and offer only the returned times.",
        )
    service = _find_service(ctx, args.service)
    if service is None:
        return ToolResult(status="invalid", message="Unknown service.")
    staff_id, start = _parse_slot(args.slot_id)
    staff = ctx.db.get(Staff, staff_id)
    if staff is None:
        return ToolResult(status="invalid", message="Unknown staff member in slot.")
    phone = args.phone or (ctx.call.caller_number if ctx.call else "")
    if not normalize_phone(phone) and not normalize_email(args.email):
        return ToolResult(
            status="invalid", message="Ask for a phone number or email for the booking."
        )
    if not args.caller_confirmed:
        return ToolResult(
            status="needs_confirmation",
            message="Read these details back and get a clear yes, then call again with "
            "caller_confirmed=true: "
            + _readback(ctx, service.name, staff.name, start, args.customer_name, args.email),
        )
    try:
        appt, created = booking_svc.book(
            ctx.db,
            ctx.calendar,
            ctx.settings,
            booking_svc.BookingRequest(
                service_id=service.id,
                staff_id=staff_id,
                start_utc=start,
                customer_name=args.customer_name,
                phone=phone,
                email=args.email,
                call_id=ctx.call.id if ctx.call else None,
                notes=args.notes,
            ),
            now_utc=ctx.now,
        )
    except booking_svc.BookingError as exc:
        status: ToolStatus = "unavailable" if exc.code == "slot_unavailable" else "error"
        return ToolResult(
            status=status,
            message=exc.message + " Apologise, then check availability again and offer other times."
            if status == "unavailable"
            else exc.message,
            data={"code": exc.code},
        )
    return ToolResult(
        status="ok",
        message=(
            "Booked. Confirm it to the caller"
            + (" and say a confirmation email is on its way." if appt.email else ".")
        ),
        data={
            "appointment_ref": str(appt.id)[:8],
            "service": appt.service.name,
            "staff": appt.staff.name,
            "when": speak_time(appt.start_utc, ctx.tz),
            "start_utc": appt.start_utc.isoformat(),
            "already_existed": not created,
        },
    )


def _find(ctx: ToolContext, args: FindIn) -> tuple[ToolResult | None, Any]:
    try:
        on = _resolve(ctx, args.date)
    except ValueError as exc:
        return ToolResult(status="invalid", message=str(exc)), None
    matches = booking_svc.find_bookings(
        ctx.db, contact=args.contact, on_date=on.date, tz=ctx.tz, now_utc=ctx.now
    )
    try:
        appt = booking_svc.resolve_one(matches, args.appointment_ref)
    except booking_svc.BookingError as exc:
        if exc.code == "multiple_matches":
            return ToolResult(
                status="needs_confirmation",
                message="Several bookings match. Ask which one, then call again with its "
                "appointment_ref.",
                data={
                    "bookings": [
                        {
                            "appointment_ref": str(a.id)[:8],
                            "service": a.service.name,
                            "when": speak_time(a.start_utc, ctx.tz),
                        }
                        for a in matches
                    ]
                },
            ), None
        return ToolResult(status="not_found", message=exc.message), None
    return None, appt


def reschedule_appointment(ctx: ToolContext, args: RescheduleIn) -> ToolResult:
    err, appt = _find(ctx, args)
    if err:
        return err
    if not _offered_in_call(ctx, args.new_slot_id):
        return ToolResult(
            status="invalid",
            message="The new time was not offered by check_availability in this call. Check "
            "availability for the new date first.",
            data={
                "current": {
                    "service": appt.service.name,
                    "when": speak_time(appt.start_utc, ctx.tz),
                }
            },
        )
    staff_id, start = _parse_slot(args.new_slot_id)
    new_staff = ctx.db.get(Staff, staff_id)
    if not args.caller_confirmed:
        return ToolResult(
            status="needs_confirmation",
            message=(
                f"Read back: move {appt.service.name} from {speak_time(appt.start_utc, ctx.tz)} "
                f"to {speak_time(start, ctx.tz)} with {new_staff.name if new_staff else 'staff'}. "
                "Get a clear yes, then call again with caller_confirmed=true."
            ),
            data={"appointment_ref": str(appt.id)[:8]},
        )
    try:
        appt = booking_svc.reschedule(
            ctx.db,
            ctx.calendar,
            ctx.settings,
            appt,
            new_start_utc=start,
            new_staff_id=staff_id,
            now_utc=ctx.now,
        )
    except booking_svc.BookingError as exc:
        return ToolResult(
            status="unavailable" if exc.code == "slot_unavailable" else "error",
            message=exc.message,
            data={"code": exc.code},
        )
    return ToolResult(
        status="ok",
        message="Moved. Confirm the new time to the caller.",
        data={
            "appointment_ref": str(appt.id)[:8],
            "service": appt.service.name,
            "staff": appt.staff.name,
            "when": speak_time(appt.start_utc, ctx.tz),
        },
    )


def cancel_appointment(ctx: ToolContext, args: CancelIn) -> ToolResult:
    err, appt = _find(ctx, args)
    if err:
        return err
    if not args.caller_confirmed:
        return ToolResult(
            status="needs_confirmation",
            message=(
                f"Read back: cancel {appt.service.name} on {speak_time(appt.start_utc, ctx.tz)}. "
                "Get a clear yes, then call again with caller_confirmed=true."
            ),
            data={"appointment_ref": str(appt.id)[:8]},
        )
    try:
        appt = booking_svc.cancel(ctx.db, ctx.calendar, ctx.settings, appt)
    except booking_svc.BookingError as exc:
        return ToolResult(status="error", message=exc.message, data={"code": exc.code})
    return ToolResult(
        status="ok",
        message="Cancelled. Confirm to the caller and offer to book another time.",
        data={
            "appointment_ref": str(appt.id)[:8],
            "service": appt.service.name,
            "when": speak_time(appt.start_utc, ctx.tz),
        },
    )


def _store_message(
    ctx: ToolContext, *, name: str, number: str, text: str, urgent: bool, key: str
) -> Message:
    existing = ctx.db.scalar(select(Message).where(Message.idempotency_key == key))
    if existing:
        return existing
    msg = Message(
        call_id=ctx.call.id if ctx.call else None,
        name=name,
        callback_number=number,
        text=text,
        urgent=urgent,
        idempotency_key=key,
    )
    ctx.db.add(msg)
    ctx.db.flush()
    enqueue(
        ctx.db, "send_staff_message", {"message_id": msg.id}, idempotency_key=f"staffmsg:{msg.id}"
    )
    ctx.db.commit()
    return msg


def take_message(ctx: ToolContext, args: MessageIn) -> ToolResult:
    scope = str(ctx.call.id) if ctx.call else uuid.uuid4().hex
    digest = hashlib.sha256(args.message.encode()).hexdigest()[:12]
    key = f"msg:{scope}:{normalize_phone(args.callback_number)}:{digest}"
    _store_message(
        ctx,
        name=args.name,
        number=normalize_phone(args.callback_number),
        text=args.message,
        urgent=args.urgent,
        key=key,
    )
    return ToolResult(
        status="ok",
        message="Message saved and the team has been notified. Tell the caller someone will "
        "call them back.",
    )


def request_human(ctx: ToolContext, args: HumanIn) -> ToolResult:
    number = normalize_phone(args.callback_number) or (
        normalize_phone(ctx.call.caller_number) if ctx.call else ""
    )
    handoff = ctx.biz.handoff_number or ctx.settings.handoff_number
    if ctx.settings.transfer_enabled and handoff and ctx.call and ctx.call.channel == "phone":
        return ToolResult(
            status="transferred",
            message="Tell the caller you're connecting them now. The transfer is in progress.",
            data={"transfer_to": handoff},
        )
    if not number:
        return ToolResult(
            status="invalid",
            message="Ask for the best number for a team member to call them back.",
        )
    scope = str(ctx.call.id) if ctx.call else uuid.uuid4().hex
    _store_message(
        ctx, name=args.name, number=number, text=args.reason, urgent=True, key=f"human:{scope}"
    )
    return ToolResult(
        status="ok",
        message="A team member has been alerted and will call back as soon as possible. "
        "Tell the caller that, and ask if there is anything else.",
    )


TOOLS = {
    "get_business_info": get_business_info,
    "answer_faq": answer_faq,
    "check_availability": check_availability,
    "book_appointment": book_appointment,
    "reschedule_appointment": reschedule_appointment,
    "cancel_appointment": cancel_appointment,
    "take_message": take_message,
    "request_human": request_human,
}


def run_tool(ctx: ToolContext, tool: str, raw_args: dict[str, Any]) -> ToolResult:
    """Validate, run and record a tool call (with personal data redacted)."""
    started = _time.perf_counter()
    if tool not in TOOLS:
        return ToolResult(status="invalid", message=f"Unknown tool {tool}")
    try:
        args = TOOL_INPUTS[tool].model_validate(raw_args)
        result = TOOLS[tool](ctx, args)  # type: ignore[operator]
    except ValidationError as exc:
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        result = ToolResult(status="invalid", message=f"Invalid or missing: {fields}")
    except Exception:
        ctx.db.rollback()
        result = ToolResult(
            status="error",
            message="Something went wrong. Apologise, retry once, then offer to take a message.",
        )
        _record(ctx, tool, raw_args, result, started)
        raise
    _record(ctx, tool, raw_args, result, started)
    return result


def _record(
    ctx: ToolContext, tool: str, raw_args: dict[str, Any], result: ToolResult, started: float
) -> None:
    if ctx.call is None:
        return
    summary = ""
    if result.status == "ok":
        d = result.data
        summary = {
            "check_availability": f"{len(d.get('slots', []))} slots for {d.get('service')}",
            "book_appointment": f"{d.get('service')} with {d.get('staff')}, {d.get('when')}",
            "reschedule_appointment": f"Moved to {d.get('when')}",
            "cancel_appointment": f"Cancelled {d.get('service')} on {d.get('when')}",
            "answer_faq": str(d.get("question", "")),
            "take_message": "Message saved for staff",
            "request_human": "Staff alerted (urgent)",
        }.get(tool, "")
    result_data: dict[str, Any] = {}
    if tool == "check_availability" and result.status == "ok":
        result_data = {
            "slot_ids": result.data.get("slot_ids", []),
            "spoken": [s["spoken"] for s in result.data.get("slots", [])],
        }
    elif "appointment_ref" in result.data:
        result_data = {"appointment_ref": result.data["appointment_ref"]}
    ctx.db.add(
        ToolCall(
            call_id=ctx.call.id,
            tool=tool,
            args=redact(raw_args),
            result_status=result.status,
            result_summary=summary or result.message[:200],
            result_data=result_data,
            latency_ms=int((_time.perf_counter() - started) * 1000),
        )
    )
    ctx.db.commit()


TOOL_DESCRIPTIONS = {
    "get_business_info": "Opening hours, address, services with prices and durations, and staff.",
    "answer_faq": "Look up the salon's FAQ (parking, payment, policies, products...).",
    "check_availability": "Find free appointment times. Only times returned here may be offered.",
    "book_appointment": "Book a slot from check_availability. Set caller_confirmed=true only "
    "after reading back the details and hearing a clear yes.",
    "reschedule_appointment": "Move the caller's booking (found by their phone or email and the "
    "booking date) to a new slot from check_availability.",
    "cancel_appointment": "Cancel the caller's booking (found by their phone or email and date).",
    "take_message": "Save a message for the team; they get an email.",
    "request_human": "Hand off to a person when the caller asks or you can't help.",
}
