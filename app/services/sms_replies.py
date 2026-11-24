"""What happens when a customer texts back.

- "YES" takes a time held for them from the waitlist.
- "C" cancels their next appointment (only when exactly one is coming up, so a text can
  never cancel the wrong booking).
- Anything else gets a short help text. Carrier keywords such as STOP are handled by Twilio.

The reply is returned as text (sent back as TwiML), so changes made by text are confirmed
in the same conversation instead of by a second message.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import BusinessConfig
from app.services import booking as booking_svc
from app.services import waitlist
from app.services.calendar import CalendarClient


def _when(dt: datetime, tz: str) -> str:
    local = dt.astimezone(ZoneInfo(tz))
    return f"{local:%a %d %b} at {local:%I:%M %p}".replace(" 0", " ")


def handle_reply(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    *,
    phone: str,
    text: str,
    now: datetime,
) -> str:
    biz = db.get(BusinessConfig, 1)
    name = biz.name if biz else "We"
    tz = biz.timezone if biz else "UTC"
    call_us = f" Call us on {biz.phone}." if biz and biz.phone else ""
    word = text.strip().upper().rstrip(".!")

    if word in {"YES", "Y"}:
        entry = waitlist.open_offer_for_phone(db, phone, now)
        if entry is None:
            return f"{name}: there's no time held for you right now.{call_us}"
        try:
            appt = waitlist.accept_offer(db, calendar, settings, entry, now, confirm_sms=False)
        except booking_svc.BookingError:
            return f"{name}: sorry, that time was just taken. You're still on the waitlist."
        return (
            f"{name}: booked! {appt.service.name} with {appt.staff.name}, "
            f"{_when(appt.start_utc, tz)}. Reply C to cancel."
        )

    if word == "C":
        upcoming = booking_svc.find_bookings(db, contact=phone, on_date=None, tz=tz, now_utc=now)
        if not upcoming:
            return f"{name}: we couldn't find an upcoming booking for this number.{call_us}"
        if len(upcoming) > 1:
            return (
                f"{name}: you have {len(upcoming)} upcoming bookings, so we can't tell which "
                f"to cancel by text.{call_us}"
            )
        appt = upcoming[0]
        try:
            booking_svc.cancel(db, calendar, settings, appt, confirm_sms=False)
        except booking_svc.BookingError:
            return f"{name}: sorry, we couldn't cancel it just now.{call_us}"
        return f"{name}: your {appt.service.name} on {_when(appt.start_utc, tz)} is cancelled."

    return f"{name}: reply C to cancel your next appointment.{call_us}"
