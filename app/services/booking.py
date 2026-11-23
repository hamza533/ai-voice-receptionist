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
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.jobs.queue import enqueue
from app.models import ACTIVE_APPOINTMENT_STATUSES, Appointment, BusinessConfig, Service, Staff
from app.services.availability import slot_is_free
from app.services.calendar import CalendarClient, calendar_for_staff, event_id_for
from app.services.privacy import normalize_email, normalize_phone, phones_match
from app.services.timeutil import speak_time

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


def _enqueue_customer_email(db: Session, appt: Appointment, change: str) -> None:
    if not appt.email:
        return
    enqueue(
        db,
        "send_booking_email",
        {"appointment_id": str(appt.id), "change": change},
        idempotency_key=f"email:{appt.id}:{change}:{appt.start_utc.isoformat()}",
    )


def book(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    req: BookingRequest,
    *,
    now_utc: datetime,
) -> tuple[Appointment, bool]:
    """Create a booking. Returns (appointment, created). Commits on success."""
    key = booking_key(req.call_id, req.staff_id, req.start_utc)
    existing = db.scalar(select(Appointment).where(Appointment.idempotency_key == key))
    if existing is not None:
        if existing.status != "cancelled":
            return existing, False
        # Booked, cancelled, then booked again in the same call: a genuinely new booking.
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

    cal_id = calendar_for_staff(staff, settings.google_calendar_id)
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

    _enqueue_customer_email(db, appt, "booked")
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            calendar.delete_event(cal_id, event_id)
        except Exception:
            log.exception("could not roll back calendar event")
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
    if appointment_ref:
        ref = appointment_ref.strip().lower()
        chosen = [a for a in matches if str(a.id).startswith(ref)]
        if len(chosen) == 1:
            return chosen[0]
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
    old_cal = calendar_for_staff(appt.staff, settings.google_calendar_id)
    new_cal = calendar_for_staff(staff, settings.google_calendar_id)
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

    event_id = appt.calendar_event_id or event_id_for(appt.idempotency_key)
    summary, desc = _event_text(appt, tz)
    try:
        if old_cal != new_cal:
            calendar.delete_event(old_cal, event_id)
        appt.calendar_event_id = calendar.upsert_event(
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

    _enqueue_customer_email(db, appt, "rescheduled")
    db.commit()
    return appt


def cancel(
    db: Session, calendar: CalendarClient, settings: Settings, appt: Appointment
) -> Appointment:
    if appt.status == "cancelled":
        return appt
    cal_id = calendar_for_staff(appt.staff, settings.google_calendar_id)
    if appt.calendar_event_id:
        try:
            calendar.delete_event(cal_id, appt.calendar_event_id)
        except Exception as exc:
            log.exception("calendar delete failed on cancel")
            raise BookingError("calendar_error", "The calendar could not be updated.") from exc
    appt.status = "cancelled"
    _enqueue_customer_email(db, appt, "cancelled")
    db.commit()
    return appt
