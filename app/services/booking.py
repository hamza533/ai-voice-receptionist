"""Booking, rescheduling and cancelling. The API owns all business rules.

Double-booking protection, in three layers:
1. the staff row is locked (SELECT ... FOR UPDATE) for the duration of the booking step,
2. the exact slot is re-checked against bookings and the calendar inside that lock,
3. a partial unique index on (staff_id, start_utc) for active bookings.

Every booking carries an idempotency key (call + staff + start), so a retried tool call
returns the existing booking instead of creating a second one, and the calendar event id
is derived from the same key.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.jobs.queue import enqueue
from app.models import (
    ACTIVE_APPOINTMENT_STATUSES,
    Appointment,
    BusinessConfig,
    Service,
    Staff,
    WaitlistEntry,
)
from app.services.availability import slot_is_free
from app.services.calendar import (
    CalendarClient,
    calendar_for_staff,
    default_calendar_id,
    event_id_for,
)
from app.services.privacy import normalize_email, normalize_phone, phones_match
from app.services.timeutil import speak_time, utcnow

log = logging.getLogger(__name__)


class BookingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class BookingRequest:
    service_id: int
    staff_id: int
    start_utc: datetime
    customer_name: str
    phone: str = ""
    email: str = ""
    call_id: uuid.UUID | None = None
    notes: str = ""


def booking_key(call_id: uuid.UUID | None, staff_id: int, start_utc: datetime) -> str:
    scope = str(call_id) if call_id else "manual"
    return f"book:{scope}:{staff_id}:{start_utc.strftime('%Y%m%dT%H%M')}"


def _tz(db: Session) -> str:
    biz = db.get(BusinessConfig, 1)
    return biz.timezone if biz else "UTC"


def _lock_staff(db: Session, staff_id: int) -> Staff:
    staff = db.execute(
        select(Staff).where(Staff.id == staff_id).with_for_update()
    ).scalar_one_or_none()
    if staff is None:
        raise BookingError("unknown_staff", "That staff member does not exist.")
    return staff


def _event_text(appt: Appointment, tz: str) -> tuple[str, str]:
    summary = f"{appt.service.name} – {appt.customer_name}"
    desc = (
        f"Booked by the AI receptionist.\nService: {appt.service.name}\n"
        f"With: {appt.staff.name}\nWhen: {speak_time(appt.start_utc, tz)}\n"
        f"Phone: {appt.phone or '-'}\nEmail: {appt.email or '-'}\nRef: {str(appt.id)[:8]}"
    )
    return summary, desc


def _notify_customer(
    db: Session, appt: Appointment, change: str, *, confirm_sms: bool = True
) -> None:
    """Queue the customer's confirmation email and text, and the reminder text, in the same
    transaction as the booking change (transactional outbox). The job handlers check the
    business's notification settings and skip what is switched off."""
    payload = {"appointment_id": str(appt.id), "change": change}
    stamp = appt.start_utc.isoformat()
    if appt.email:
        enqueue(
            db, "send_booking_email", payload, idempotency_key=f"email:{appt.id}:{change}:{stamp}"
        )
    if not appt.phone:
        return
    if confirm_sms:  # False when the customer made the change by text: the reply confirms it
        enqueue(db, "send_booking_sms", payload, idempotency_key=f"sms:{appt.id}:{change}:{stamp}")
    if change in {"booked", "rescheduled"}:
        biz = db.get(BusinessConfig, 1)
        hours = biz.reminder_hours if biz else 24
        run_at = appt.start_utc - timedelta(hours=hours)
        if run_at > utcnow():
            enqueue(
                db,
                "send_reminder",
                {"appointment_id": str(appt.id), "start_utc": stamp},
                idempotency_key=f"reminder:{appt.id}:{stamp}",
                run_at=run_at,
            )


def _slot_freed(db: Session, staff_id: int, start_utc: datetime) -> None:
    """A cancelled or moved booking frees its time: offer it to the waitlist."""
    if start_utc <= utcnow():
        return
    enqueue(
        db,
        "waitlist_match",
        {"staff_id": staff_id, "start_utc": start_utc.isoformat()},
        idempotency_key=f"waitlist:{staff_id}:{start_utc.isoformat()}:{uuid.uuid4().hex[:8]}",
    )


def _close_waitlist(db: Session, appt: Appointment, tz: str) -> None:
    """Someone on the waitlist who books that day by any route is no longer waiting."""
    if not appt.phone:
        return
    day = appt.start_utc.astimezone(ZoneInfo(tz)).date()
    rows = db.scalars(
        select(WaitlistEntry).where(
            WaitlistEntry.day == day, WaitlistEntry.status.in_(("waiting", "offered"))
        )
    )
    ids = [w.id for w in rows if phones_match(w.phone, appt.phone)]
    if ids:
        db.execute(
            update(WaitlistEntry)
            .where(WaitlistEntry.id.in_(ids))
            .values(status="booked", appointment_id=appt.id, offer_expires_at=None)
        )


def book(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    req: BookingRequest,
    *,
    now_utc: datetime,
    confirm_sms: bool = True,
) -> tuple[Appointment, bool]:
    """Create a booking. Returns (appointment, created). Commits on success."""
    key = booking_key(req.call_id, req.staff_id, req.start_utc)
    existing = db.scalar(select(Appointment).where(Appointment.idempotency_key == key))
    if existing is not None:
        if existing.status == "booked":
            return existing, False  # a retried tool call: same booking, same time
        # Cancelled or moved since (same call): this time slot is a genuinely new booking.
        key = f"{key}:{uuid.uuid4().hex[:8]}"

    phone = normalize_phone(req.phone)
    email = normalize_email(req.email)
    if not req.customer_name.strip():
        raise BookingError("missing_name", "The caller's name is required.")
    if not phone and not email:
        raise BookingError("missing_contact", "A phone number or email is required.")

    service = db.get(Service, req.service_id)
    if service is None or not service.active:
        raise BookingError("unknown_service", "That service is not offered.")

    staff = _lock_staff(db, req.staff_id)
    free, reason = slot_is_free(
        db,
        calendar,
        settings,
        service=service,
        staff=staff,
        start_utc=req.start_utc,
        now_utc=now_utc,
    )
    if not free:
        db.rollback()
        raise BookingError("slot_unavailable", f"That time is no longer available ({reason}).")

    tz = _tz(db)
    appt = Appointment(
        service_id=service.id,
        staff_id=staff.id,
        start_utc=req.start_utc,
        end_utc=req.start_utc + timedelta(minutes=service.duration_min),
        customer_name=req.customer_name.strip()[:120],
        phone=phone,
        email=email,
        status="booked",
        idempotency_key=key,
        call_id=req.call_id,
        notes=req.notes[:1000],
    )
    appt.service = service
    appt.staff = staff
    db.add(appt)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        # Either the same request raced us (idempotency key) or the slot was taken.
        again = db.scalar(select(Appointment).where(Appointment.idempotency_key == key))
        if again is not None:
            return again, False
        raise BookingError("slot_unavailable", "That time was just taken.") from exc

    cal_id = calendar_for_staff(staff, default_calendar_id(settings))
    summary, desc = _event_text(appt, tz)
    event_id = event_id_for(key)
    try:
        appt.calendar_event_id = calendar.upsert_event(
            cal_id,
            event_id,
            summary=summary,
            description=desc,
            start=appt.start_utc,
            end=appt.end_utc,
            staff_id=staff.id,
            timezone=tz,
        )
    except Exception as exc:
        db.rollback()
        log.exception("calendar event creation failed", extra={"staff_id": staff.id})
        raise BookingError("calendar_error", "The calendar could not be updated.") from exc

    _notify_customer(db, appt, "booked", confirm_sms=confirm_sms)
    _close_waitlist(db, appt, tz)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _try(calendar.delete_event, cal_id, event_id)
        raise
    return appt, True


# ---------------------------------------------------------------- lookup


def find_bookings(
    db: Session,
    *,
    contact: str,
    on_date: date | None,
    tz: str,
    now_utc: datetime,
) -> list[Appointment]:
    """Active future bookings whose phone or email matches `contact`.

    The contact must match: a caller can never see or change someone else's booking.
    """
    email = normalize_email(contact)
    phone = "" if email else normalize_phone(contact)
    if not email and not phone:
        return []
    stmt = select(Appointment).where(
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.end_utc > now_utc,
    )
    if on_date is not None:
        zone = ZoneInfo(tz)
        lo = datetime.combine(on_date, time.min, tzinfo=zone)
        stmt = stmt.where(
            Appointment.start_utc >= lo, Appointment.start_utc < lo + timedelta(days=1)
        )
    if email:
        stmt = stmt.where(Appointment.email == email)
    matches = []
    for appt in db.scalars(stmt.order_by(Appointment.start_utc)):
        if email or phones_match(appt.phone, phone):
            matches.append(appt)
    return matches


def resolve_one(matches: list[Appointment], appointment_ref: str | None) -> Appointment:
    ref = (appointment_ref or "").strip().lower()
    if ref:
        # A reference was given: it must pick exactly one of the caller's bookings. Never fall
        # back to "their only booking", or a mis-heard reference changes the wrong one.
        matches = [a for a in matches if str(a.id).startswith(ref)]
        if not matches:
            raise BookingError(
                "not_found",
                "No booking with that reference matches the caller's details. Check the "
                "reference, or look the booking up by date without it.",
            )
    if not matches:
        raise BookingError(
            "not_found",
            "No booking matches that contact and date. Ask the caller to check the phone "
            "number or email used when booking.",
        )
    if len(matches) > 1:
        raise BookingError("multiple_matches", "More than one booking matches.")
    return matches[0]


# ---------------------------------------------------------------- reschedule & cancel


def reschedule(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    appt: Appointment,
    *,
    new_start_utc: datetime,
    new_staff_id: int | None,
    now_utc: datetime,
) -> Appointment:
    staff_id = new_staff_id or appt.staff_id
    if appt.start_utc == new_start_utc and appt.staff_id == staff_id:
        return appt  # idempotent: already there

    staff = _lock_staff(db, staff_id)
    service = appt.service
    free, reason = slot_is_free(
        db,
        calendar,
        settings,
        service=service,
        staff=staff,
        start_utc=new_start_utc,
        now_utc=now_utc,
        exclude_appointment_id=appt.id,
    )
    if not free:
        db.rollback()
        raise BookingError("slot_unavailable", f"That time is not available ({reason}).")

    tz = _tz(db)
    event_id = appt.calendar_event_id or event_id_for(appt.idempotency_key)
    old = _EventState.of(appt, settings, tz)
    new_cal = calendar_for_staff(staff, default_calendar_id(settings))
    appt.staff_id = staff.id
    appt.staff = staff
    appt.start_utc = new_start_utc
    appt.end_utc = new_start_utc + timedelta(minutes=service.duration_min)
    appt.status = "rescheduled"
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise BookingError("slot_unavailable", "That time was just taken.") from exc

    summary, desc = _event_text(appt, tz)
    try:
        # Write the new event before removing the old one: a failure part-way must leave
        # the booking visible in a calendar, never in none.
        new_event_id = calendar.upsert_event(
            new_cal,
            event_id,
            summary=summary,
            description=desc,
            start=appt.start_utc,
            end=appt.end_utc,
            staff_id=staff.id,
            timezone=tz,
        )
    except Exception as exc:
        db.rollback()
        log.exception("calendar update failed on reschedule")
        raise BookingError("calendar_error", "The calendar could not be updated.") from exc

    appt.calendar_event_id = new_event_id
    _notify_customer(db, appt, "rescheduled")
    _slot_freed(db, old.staff_id, old.start)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if old.calendar_id != new_cal:
            _try(calendar.delete_event, new_cal, event_id)
        else:
            old.restore(calendar, event_id)
        raise
    if old.calendar_id != new_cal:
        # The database already holds the new time; a leftover old event only looks busy.
        _try(calendar.delete_event, old.calendar_id, event_id)
    return appt


def cancel(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    appt: Appointment,
    *,
    confirm_sms: bool = True,
) -> Appointment:
    if appt.status == "cancelled":
        return appt
    event_id = appt.calendar_event_id
    old = _EventState.of(appt, settings, _tz(db))
    if event_id:
        try:
            calendar.delete_event(old.calendar_id, event_id)
        except Exception as exc:
            log.exception("calendar delete failed on cancel")
            raise BookingError("calendar_error", "The calendar could not be updated.") from exc
    appt.status = "cancelled"
    _notify_customer(db, appt, "cancelled", confirm_sms=confirm_sms)
    _slot_freed(db, appt.staff_id, appt.start_utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if event_id:
            old.restore(calendar, event_id)  # the booking is still active: put it back
        raise
    return appt


@dataclass(frozen=True)
class _EventState:
    """An appointment's calendar event as it was, to undo a calendar change when the
    database commit that should follow it fails."""

    calendar_id: str
    summary: str
    description: str
    start: datetime
    end: datetime
    staff_id: int
    timezone: str

    @classmethod
    def of(cls, appt: Appointment, settings: Settings, tz: str) -> _EventState:
        summary, desc = _event_text(appt, tz)
        return cls(
            calendar_id=calendar_for_staff(appt.staff, default_calendar_id(settings)),
            summary=summary,
            description=desc,
            start=appt.start_utc,
            end=appt.end_utc,
            staff_id=appt.staff_id,
            timezone=tz,
        )

    def restore(self, calendar: CalendarClient, event_id: str) -> None:
        _try(
            calendar.upsert_event,
            self.calendar_id,
            event_id,
            summary=self.summary,
            description=self.description,
            start=self.start,
            end=self.end,
            staff_id=self.staff_id,
            timezone=self.timezone,
        )


def _try(fn: Callable[..., object], *args: object, **kwargs: object) -> None:
    """Best-effort calendar clean-up: log failures, never raise over the original error."""
    try:
        fn(*args, **kwargs)
    except Exception:
        log.exception("calendar clean-up failed", extra={"op": getattr(fn, "__name__", "")})
