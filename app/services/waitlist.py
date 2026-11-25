"""Waitlist: callers who want a day that is full get the next matching cancellation.

Flow: a booking is cancelled or moved -> a `waitlist_match` job looks for the first person
waiting for that day (right service, staff and time of day) whose booking would fit the
freed time -> they are offered it by text and it is held for `waitlist_hold_minutes`.
They reply YES (or staff press "Book" in the dashboard) to take it; the booking goes
through the normal booking step, so all double-booking guarantees still apply. If the hold
runs out, the next person is offered the same time.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.jobs.queue import enqueue
from app.models import Appointment, BusinessConfig, Service, Staff, WaitlistEntry
from app.services import booking as booking_svc
from app.services.availability import find_slots, slot_is_free
from app.services.calendar import CalendarClient
from app.services.privacy import normalize_phone, phones_match
from app.services.timeutil import TIME_WINDOWS, local_today

log = logging.getLogger(__name__)


def slot_key(staff_id: int, start_utc: datetime) -> str:
    return f"{staff_id}:{start_utc.astimezone(UTC).strftime('%Y%m%dT%H%MZ')}"


def fits_window(time_of_day: str, local_start: time) -> bool:
    lo, hi = TIME_WINDOWS.get(time_of_day, (None, None))
    return (lo is None or local_start >= lo) and (hi is None or local_start < hi)


def add_entry(
    db: Session,
    *,
    name: str,
    phone: str,
    service: Service,
    day: date,
    staff: Staff | None = None,
    time_of_day: str = "any",
    notes: str = "",
    call_id: object | None = None,
) -> tuple[WaitlistEntry, bool]:
    """Add someone to the waitlist. Returns (entry, created); the same person waiting for
    the same service and day is not added twice."""
    number = normalize_phone(phone)
    existing = db.scalars(
        select(WaitlistEntry).where(
            WaitlistEntry.day == day,
            WaitlistEntry.service_id == service.id,
            WaitlistEntry.status.in_(("waiting", "offered")),
        )
    )
    for e in existing:
        if phones_match(e.phone, number):
            return e, False
    entry = WaitlistEntry(
        name=name.strip()[:120],
        phone=number,
        service_id=service.id,
        staff_id=staff.id if staff else None,
        day=day,
        time_of_day=time_of_day if time_of_day in TIME_WINDOWS else "any",
        notes=notes[:500],
        status="waiting",
        call_id=call_id,
        offered_slots=[],
    )
    db.add(entry)
    db.commit()
    return entry, True


def match_freed_slot(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    *,
    staff_id: int,
    start_utc: datetime,
    now: datetime,
) -> WaitlistEntry | None:
    """Offer a freed time to the first suitable person waiting. Commits the offer and queues
    the offer text and the hold expiry in the same transaction."""
    biz = db.get(BusinessConfig, 1)
    if biz is None or not biz.waitlist_enabled:
        return None
    # Lock the staff row (as booking does) so two jobs for the same freed time can't both
    # offer it, then skip the time if someone already holds it.
    staff = db.execute(
        select(Staff).where(Staff.id == staff_id).with_for_update()
    ).scalar_one_or_none()
    if staff is None or not staff.active or _held(db, staff_id, start_utc, now):
        db.rollback()
        return None
    local = start_utc.astimezone(ZoneInfo(biz.timezone))
    key = slot_key(staff_id, start_utc)
    waiting = db.scalars(
        select(WaitlistEntry)
        .where(WaitlistEntry.day == local.date(), WaitlistEntry.status == "waiting")
        .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
    )
    for entry in waiting:
        if entry.staff_id not in (None, staff_id) or key in (entry.offered_slots or []):
            continue
        if not fits_window(entry.time_of_day, local.time()):
            continue
        free, _ = slot_is_free(
            db,
            calendar,
            settings,
            service=entry.service,
            staff=staff,
            start_utc=start_utc,
            now_utc=now,
        )
        if not free:
            continue
        expires = now + timedelta(minutes=biz.waitlist_hold_minutes)
        entry.status = "offered"
        entry.offer_staff_id = staff_id
        entry.offer_start_utc = start_utc
        entry.offer_expires_at = expires
        entry.offered_slots = [*(entry.offered_slots or []), key]
        enqueue(
            db,
            "send_waitlist_offer",
            {"entry_id": entry.id, "slot": key},
            idempotency_key=f"waitlist-offer:{entry.id}:{key}",
        )
        enqueue(
            db,
            "waitlist_expire",
            {"entry_id": entry.id, "slot": key},
            idempotency_key=f"waitlist-expire:{entry.id}:{key}",
            run_at=expires,
        )
        db.commit()
        log.info("waitlist offer made", extra={"entry_id": entry.id})
        return entry
    db.rollback()
    return None


def _held(db: Session, staff_id: int, start_utc: datetime, now: datetime) -> bool:
    return (
        db.scalar(
            select(WaitlistEntry.id).where(
                WaitlistEntry.status == "offered",
                WaitlistEntry.offer_staff_id == staff_id,
                WaitlistEntry.offer_start_utc == start_utc,
                WaitlistEntry.offer_expires_at > now,
            )
        )
        is not None
    )


def sweep(db: Session, calendar: CalendarClient, settings: Settings, now: datetime) -> int:
    """Offer open times to people waiting, whatever freed them: time off removed, hours
    widened, a closure or calendar event deleted (cancellations are matched immediately).
    Runs every 15 minutes. Returns the number of offers made."""
    biz = db.get(BusinessConfig, 1)
    if biz is None or not biz.waitlist_enabled:
        return 0
    zone = ZoneInfo(biz.timezone)
    today = local_today(biz.timezone, now)
    last = today + timedelta(days=settings.booking_window_days)
    entries = list(
        db.scalars(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.status == "waiting",
                WaitlistEntry.day >= today,
                WaitlistEntry.day <= last,
            )
            .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
        )
    )
    offers = 0
    for entry in entries:
        db.refresh(entry)
        if entry.status != "waiting":  # offered a time earlier in this sweep
            continue
        after, before = TIME_WINDOWS.get(entry.time_of_day, (None, None))
        slots = find_slots(
            db,
            calendar,
            settings,
            service=entry.service,
            date_from=entry.day,
            date_to=entry.day,
            staff_id=entry.staff_id,
            now_utc=now,
            after_local_time=after,
            before_local_time=before,
        )
        for slot in slots:
            if slot.start_utc.astimezone(zone).date() != entry.day:
                continue
            if slot_key(slot.staff_id, slot.start_utc) in (entry.offered_slots or []):
                continue
            made = match_freed_slot(
                db, calendar, settings, staff_id=slot.staff_id, start_utc=slot.start_utc, now=now
            )
            if made is not None:
                offers += 1
                break
    return offers


def accept_offer(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    entry: WaitlistEntry,
    now: datetime,
    *,
    confirm_sms: bool = True,
) -> Appointment:
    """Book the time held for this person. Raises BookingError if it is no longer free (the
    person goes back to waiting)."""
    if entry.status != "offered" or not entry.offer_start_utc or not entry.offer_staff_id:
        raise booking_svc.BookingError("no_offer", "There is no time held for this person.")
    if entry.offer_expires_at and entry.offer_expires_at < now:
        raise booking_svc.BookingError("offer_expired", "The held time has expired.")
    entry_id, phone = entry.id, entry.phone
    try:
        appt, _ = booking_svc.book(
            db,
            calendar,
            settings,
            booking_svc.BookingRequest(
                service_id=entry.service_id,
                staff_id=entry.offer_staff_id,
                start_utc=entry.offer_start_utc,
                customer_name=entry.name,
                phone=phone,
                notes="Booked from the waitlist",
            ),
            now_utc=now,
            confirm_sms=confirm_sms,
        )
    except booking_svc.BookingError:
        back = db.get(WaitlistEntry, entry_id)
        if back is not None:
            back.status = "waiting"
            back.offer_expires_at = None
            db.commit()
        raise
    done = db.get(WaitlistEntry, entry_id)
    if done is not None and done.status != "booked":  # book() closes entries by phone + day
        done.status = "booked"
        done.appointment_id = appt.id
        db.commit()
    return appt


def expire_offer(
    db: Session, entry_id: int, key: str, now: datetime
) -> tuple[int, datetime] | None:
    """The hold ran out: the person goes back to waiting (for other times) and the time is
    returned as (staff_id, start_utc) so it can be offered to the next person."""
    entry = db.get(WaitlistEntry, entry_id)
    if entry is None or entry.status != "offered" or not entry.offer_start_utc:
        return None
    if entry.offer_staff_id is None or slot_key(entry.offer_staff_id, entry.offer_start_utc) != key:
        return None
    if entry.offer_expires_at and entry.offer_expires_at > now:
        return None
    freed = (entry.offer_staff_id, entry.offer_start_utc)
    entry.status = "waiting"
    entry.offer_expires_at = None
    entry.offer_start_utc = None
    entry.offer_staff_id = None
    db.commit()
    return freed


def open_offer_for_phone(db: Session, phone: str, now: datetime) -> WaitlistEntry | None:
    rows = db.scalars(
        select(WaitlistEntry)
        .where(WaitlistEntry.status == "offered", WaitlistEntry.offer_expires_at > now)
        .order_by(WaitlistEntry.offer_expires_at)
    )
    return next((e for e in rows if phones_match(e.phone, phone)), None)


def expire_past_days(db: Session, today: date) -> int:
    rows = list(
        db.scalars(
            select(WaitlistEntry).where(
                WaitlistEntry.day < today, WaitlistEntry.status.in_(("waiting", "offered"))
            )
        )
    )
    for e in rows:
        e.status = "expired"
    db.commit()
    return len(rows)
