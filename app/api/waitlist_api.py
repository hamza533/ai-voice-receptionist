"""Dashboard waitlist: see who is waiting, add someone, book a held time, remove."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Service, Staff, User, WaitlistEntry
from app.schemas import AppointmentOut, WaitlistIn, WaitlistOut
from app.security import current_user
from app.services import booking as booking_svc
from app.services import waitlist
from app.services.calendar import get_calendar
from app.services.privacy import normalize_phone
from app.services.timeutil import utcnow

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

OPEN = ("waiting", "offered")


def waitlist_out(e: WaitlistEntry) -> WaitlistOut:
    return WaitlistOut(
        id=e.id,
        name=e.name,
        phone=e.phone,
        service=e.service.name,
        service_id=e.service_id,
        staff=e.staff.name if e.staff else None,
        day=e.day,
        time_of_day=e.time_of_day,
        notes=e.notes,
        status=e.status,
        offer_start_utc=e.offer_start_utc,
        offer_staff=e.offer_staff.name if e.offer_staff else None,
        offer_expires_at=e.offer_expires_at,
        created_at=e.created_at,
        source="ai" if e.call_id else "manual",
    )


@router.get("", response_model=list[WaitlistOut])
def list_waitlist(
    include_closed: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[WaitlistOut]:
    stmt = select(WaitlistEntry)
    if not include_closed:
        stmt = stmt.where(WaitlistEntry.status.in_(OPEN))
    rows = db.scalars(stmt.order_by(WaitlistEntry.day, WaitlistEntry.created_at).limit(500))
    return [waitlist_out(e) for e in rows]


@router.post("", response_model=WaitlistOut, status_code=201)
def add_to_waitlist(
    body: WaitlistIn, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> WaitlistOut:
    service = db.get(Service, body.service_id)
    if service is None or not service.active:
        raise HTTPException(404, "Service not found")
    staff = db.get(Staff, body.staff_id) if body.staff_id else None
    if body.staff_id and (staff is None or staff not in service.staff):
        raise HTTPException(422, "That person doesn't do this service")
    if not normalize_phone(body.phone):
        raise HTTPException(422, "Enter a phone number with at least 7 digits")
    entry, _created = waitlist.add_entry(
        db,
        name=body.name,
        phone=body.phone,
        service=service,
        day=body.day,
        staff=staff,
        time_of_day=body.time_of_day,
        notes=body.notes,
    )
    return waitlist_out(entry)


@router.post("/{entry_id}/book", response_model=AppointmentOut)
def book_held_time(
    entry_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(current_user),
) -> AppointmentOut:
    """Staff called the person back and they want the held time."""
    from app.api.dashboard import appointment_out

    entry = db.get(WaitlistEntry, entry_id)
    if entry is None:
        raise HTTPException(404, "Not on the waitlist")
    try:
        appt = waitlist.accept_offer(db, get_calendar(settings), settings, entry, utcnow())
    except booking_svc.BookingError as exc:
        raise HTTPException(409, exc.message) from exc
    return appointment_out(appt)


@router.delete("/{entry_id}", status_code=204)
def remove_from_waitlist(
    entry_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> None:
    entry = db.get(WaitlistEntry, entry_id)
    if entry is not None and entry.status in OPEN:
        entry.status = "removed"
        entry.offer_expires_at = None
        db.commit()
