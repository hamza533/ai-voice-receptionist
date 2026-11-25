"""Slot computation.

Slots = each person's working hours (their own shifts within the salon's opening hours, or
the opening hours when they have no shifts) − holidays − their time off − calendar busy
times − existing bookings (incl. buffers), sized to the service duration, from the next
bookable moment up to BOOKING_WINDOW_DAYS.

The core (`compute_slots`) is a pure function so it is easy to unit test; `find_slots`
gathers the inputs from the database and the calendar.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    ACTIVE_APPOINTMENT_STATUSES,
    Appointment,
    BusinessConfig,
    Holiday,
    OpeningHours,
    Service,
    Staff,
    TimeOff,
)
from app.services.calendar import CalendarClient, default_calendar_id, staff_busy_intervals
from app.services.timeutil import speak_time

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class Slot:
    staff_id: int
    staff_name: str
    start_utc: datetime
    end_utc: datetime

    def as_dict(self, tz: str) -> dict[str, object]:
        loc = self.start_utc.astimezone(ZoneInfo(tz))
        return {
            "slot_id": f"{self.staff_id}:{self.start_utc.strftime('%Y%m%dT%H%MZ')}",
            "staff_id": self.staff_id,
            "staff_name": self.staff_name,
            "start_utc": self.start_utc.isoformat(),
            "start_local": loc.isoformat(),
            "spoken": speak_time(self.start_utc, tz),
        }


@dataclass
class SlotQuery:
    service_minutes: int
    buffer_minutes: int
    staff: Sequence[tuple[int, str]]  # (id, name) of staff who offer the service
    hours: dict[int, list[tuple[time, time]]]  # weekday -> [(open, close)]
    holidays: set[date]
    busy: dict[int, list[Interval]] = field(default_factory=dict)  # staff_id -> intervals
    tz: str = "UTC"
    step_minutes: int = 15
    min_lead_minutes: int = 60
    window_days: int = 30
    # staff_id -> weekday -> [(start, end)]; a person missing here works the opening hours.
    staff_hours: dict[int, dict[int, list[tuple[time, time]]]] = field(default_factory=dict)


TimeRange = tuple[time, time]


def _overlaps(a_start: datetime, a_end: datetime, intervals: Iterable[Interval]) -> bool:
    return any(a_start < b_end and b_start < a_end for b_start, b_end in intervals)


def _intersect(a: Iterable[TimeRange], b: Iterable[TimeRange]) -> list[TimeRange]:
    b = list(b)
    out = [(max(s1, s2), min(e1, e2)) for s1, e1 in a for s2, e2 in b]
    return sorted((s, e) for s, e in out if s < e)


def working_hours(
    business: dict[int, list[TimeRange]],
    own: dict[int, list[TimeRange]] | None,
    weekday: int,
) -> list[TimeRange]:
    """When a person can be booked on a weekday: their shifts clipped to the salon's opening
    hours (nobody is booked while the salon is closed), or the opening hours themselves."""
    salon = sorted(business.get(weekday, []))
    if own is None:
        return salon
    return _intersect(own.get(weekday, []), salon)


def _windows(
    day: date,
    ranges: Iterable[TimeRange],
    zone: ZoneInfo,
    after: time | None,
    before: time | None,
) -> list[tuple[datetime, datetime, datetime]]:
    """(grid base, first start, end) per working range, after the caller's time filter."""
    out = []
    for open_t, close_t in ranges:
        lo = open_t if after is None else max(open_t, after)
        hi = close_t if before is None else min(close_t, before)
        if lo < hi:
            out.append(
                (
                    datetime.combine(day, open_t, tzinfo=zone),
                    datetime.combine(day, lo, tzinfo=zone),
                    datetime.combine(day, hi, tzinfo=zone),
                )
            )
    return out


def _grid(
    windows: Iterable[tuple[datetime, datetime, datetime]], step: timedelta, duration: timedelta
) -> set[datetime]:
    """Start times on the step grid (aligned to each range's own start) that fit the service."""
    starts: set[datetime] = set()
    for base, lo, hi in windows:
        start = lo
        offset = (start - base) % step
        if offset:
            start += step - offset
        while start + duration <= hi:
            starts.add(start)
            start += step
    return starts


def compute_slots(
    q: SlotQuery,
    *,
    date_from: date,
    date_to: date,
    now_utc: datetime,
    limit: int = 6,
    after_local_time: time | None = None,
    before_local_time: time | None = None,
    per_day_limit: int = 3,
    min_gap_minutes: int = 60,
) -> list[Slot]:
    """Return bookable slots in chronological order, at most `limit`.

    Offers are spread out (at most `per_day_limit` per day, `min_gap_minutes` apart) so a
    caller hears useful choices rather than six back-to-back quarter hours.
    """
    zone = ZoneInfo(q.tz)
    earliest = now_utc + timedelta(minutes=q.min_lead_minutes)
    today_local = now_utc.astimezone(zone).date()
    last_day = min(date_to, today_local + timedelta(days=q.window_days))
    day = max(date_from, today_local)
    duration = timedelta(minutes=q.service_minutes)
    occupied = timedelta(minutes=q.service_minutes + q.buffer_minutes)
    step = timedelta(minutes=q.step_minutes)

    gap = timedelta(minutes=min_gap_minutes)
    out: list[Slot] = []
    while day <= last_day and len(out) < limit:
        if day in q.holidays:
            day += timedelta(days=1)
            continue
        windows = {
            sid: _windows(
                day,
                working_hours(q.hours, q.staff_hours.get(sid), day.weekday()),
                zone,
                after_local_time,
                before_local_time,
            )
            for sid, _ in q.staff
        }
        day_count = 0
        last_offer: datetime | None = None
        for start in sorted(_grid((w for ws in windows.values() for w in ws), step, duration)):
            s_utc = start.astimezone(UTC)
            spaced = last_offer is None or s_utc - last_offer >= gap
            if s_utc < earliest or not spaced or day_count >= per_day_limit:
                continue
            for staff_id, staff_name in q.staff:
                end = start + duration
                works = any(lo <= start and end <= hi for _, lo, hi in windows[staff_id])
                if works and not _overlaps(s_utc, s_utc + occupied, q.busy.get(staff_id, [])):
                    out.append(Slot(staff_id, staff_name, s_utc, s_utc + duration))
                    day_count += 1
                    last_offer = s_utc
                    break  # one offer per time; first free staff member
            if len(out) >= limit:
                break
        day += timedelta(days=1)
    return out


# ---------------------------------------------------------------- DB-backed helpers


def load_hours(db: Session) -> dict[int, list[tuple[time, time]]]:
    hours: dict[int, list[tuple[time, time]]] = defaultdict(list)
    for row in db.scalars(select(OpeningHours)):
        hours[row.weekday].append((row.open_time, row.close_time))
    return dict(hours)


def load_holidays(db: Session) -> set[date]:
    return {h.date for h in db.scalars(select(Holiday))}


def load_staff_hours(staff: Iterable[Staff]) -> dict[int, dict[int, list[TimeRange]]]:
    """Weekly shifts for the people who have them (the rest work the opening hours)."""
    out: dict[int, dict[int, list[TimeRange]]] = {}
    for s in staff:
        if s.shifts:
            days: dict[int, list[TimeRange]] = defaultdict(list)
            for sh in s.shifts:
                days[sh.weekday].append((sh.start_time, sh.end_time))
            out[s.id] = dict(days)
    return out


def time_off_intervals(
    db: Session, staff_ids: Sequence[int], start: datetime, end: datetime, tz: str
) -> dict[int, list[Interval]]:
    """Time off in [start, end) as UTC intervals per person; weekly breaks are expanded
    on every matching local day (so they follow the business time zone across DST)."""
    zone = ZoneInfo(tz)
    out: dict[int, list[Interval]] = defaultdict(list)
    rows = db.scalars(select(TimeOff).where(TimeOff.staff_id.in_(staff_ids)))
    first = start.astimezone(zone).date() - timedelta(days=1)
    last = end.astimezone(zone).date() + timedelta(days=1)
    for t in rows:
        if t.kind == "once" and t.start_utc and t.end_utc:
            if t.start_utc < end and t.end_utc > start:
                out[t.staff_id].append((t.start_utc, t.end_utc))
        elif t.kind == "weekly" and t.start_time and t.end_time and t.weekday is not None:
            day = first
            while day <= last:
                if day.weekday() == t.weekday:
                    lo = datetime.combine(day, t.start_time, tzinfo=zone).astimezone(UTC)
                    hi = datetime.combine(day, t.end_time, tzinfo=zone).astimezone(UTC)
                    if lo < end and hi > start:
                        out[t.staff_id].append((lo, hi))
                day += timedelta(days=1)
    return dict(out)


def booked_intervals(
    db: Session,
    staff_ids: Sequence[int],
    start: datetime,
    end: datetime,
    *,
    exclude_appointment_id: object | None = None,
) -> dict[int, list[Interval]]:
    """Existing active bookings, each extended by its own service buffer."""
    stmt = select(Appointment).where(
        Appointment.staff_id.in_(staff_ids),
        Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        Appointment.start_utc < end,
        Appointment.end_utc > start - timedelta(hours=4),
    )
    busy: dict[int, list[Interval]] = defaultdict(list)
    for appt in db.scalars(stmt):
        if exclude_appointment_id is not None and appt.id == exclude_appointment_id:
            continue
        buffer = timedelta(minutes=appt.service.buffer_min if appt.service else 0)
        busy[appt.staff_id].append((appt.start_utc, appt.end_utc + buffer))
    return dict(busy)


def _our_event_ids(db: Session, ids: set[str]) -> set[str]:
    """Which of these calendar events we created for our own bookings. Matching on the ids
    the calendar returned (not on booking times) keeps the query small and still catches a
    stale copy left behind when a booking moved."""
    rows = db.scalars(
        select(Appointment.calendar_event_id).where(Appointment.calendar_event_id.in_(ids))
    )
    return {e for e in rows if e}


def eligible_staff(service: Service, staff_id: int | None = None) -> list[Staff]:
    staff = [s for s in service.staff if s.active]
    if staff_id is not None:
        staff = [s for s in staff if s.id == staff_id]
    return sorted(staff, key=lambda s: s.id)


def find_slots(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    *,
    service: Service,
    date_from: date,
    date_to: date,
    staff_id: int | None = None,
    now_utc: datetime,
    limit: int = 6,
    after_local_time: time | None = None,
    before_local_time: time | None = None,
    exclude_appointment_id: object | None = None,
) -> list[Slot]:
    biz = db.get(BusinessConfig, 1)
    tz = biz.timezone if biz else "UTC"
    staff = eligible_staff(service, staff_id)
    if not staff:
        return []
    zone = ZoneInfo(tz)
    range_start = datetime.combine(date_from, time.min, tzinfo=zone).astimezone(UTC)
    range_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)

    busy = booked_intervals(
        db,
        [s.id for s in staff],
        range_start,
        range_end,
        exclude_appointment_id=exclude_appointment_id,
    )
    cal_busy = staff_busy_intervals(
        calendar,
        staff,
        default_calendar_id=default_calendar_id(settings),
        start=range_start,
        end=range_end,
        our_events=lambda ids: _our_event_ids(db, ids),
    )
    for sid, intervals in cal_busy.items():
        busy.setdefault(sid, []).extend(intervals)
    for sid, intervals in time_off_intervals(
        db, [s.id for s in staff], range_start, range_end, tz
    ).items():
        busy.setdefault(sid, []).extend(intervals)

    q = SlotQuery(
        service_minutes=service.duration_min,
        buffer_minutes=service.buffer_min,
        staff=[(s.id, s.name) for s in staff],
        hours=load_hours(db),
        holidays=load_holidays(db),
        busy=busy,
        tz=tz,
        step_minutes=settings.slot_step_minutes,
        min_lead_minutes=settings.min_lead_minutes,
        window_days=settings.booking_window_days,
        staff_hours=load_staff_hours(staff),
    )
    return compute_slots(
        q,
        date_from=date_from,
        date_to=date_to,
        now_utc=now_utc,
        limit=limit,
        after_local_time=after_local_time,
        before_local_time=before_local_time,
    )


def slot_is_free(
    db: Session,
    calendar: CalendarClient,
    settings: Settings,
    *,
    service: Service,
    staff: Staff,
    start_utc: datetime,
    now_utc: datetime,
    exclude_appointment_id: object | None = None,
) -> tuple[bool, str]:
    """Exact re-check used inside the booking step. Returns (free, reason)."""
    biz = db.get(BusinessConfig, 1)
    tz = biz.timezone if biz else "UTC"
    zone = ZoneInfo(tz)
    if staff not in service.staff or not staff.active:
        return False, "staff_does_not_offer_service"
    if start_utc < now_utc + timedelta(minutes=settings.min_lead_minutes):
        return False, "too_soon"
    local = start_utc.astimezone(zone)
    last_day = now_utc.astimezone(zone).date() + timedelta(days=settings.booking_window_days)
    if local.date() > last_day:
        return False, "outside_booking_window"
    if local.date() in load_holidays(db):
        return False, "closed_holiday"
    end_local = local + timedelta(minutes=service.duration_min)

    def fits(ranges: Iterable[TimeRange]) -> bool:
        return any(
            datetime.combine(local.date(), o, tzinfo=zone) <= local
            and end_local <= datetime.combine(local.date(), c, tzinfo=zone)
            for o, c in ranges
        )

    salon = load_hours(db)
    if not fits(salon.get(local.weekday(), [])):
        return False, "outside_opening_hours"
    own = load_staff_hours([staff]).get(staff.id)
    if not fits(working_hours(salon, own, local.weekday())):
        return False, "staff_not_working"
    occupied_end = start_utc + timedelta(minutes=service.duration_min + service.buffer_min)
    off = time_off_intervals(db, [staff.id], start_utc, occupied_end, tz).get(staff.id, [])
    if _overlaps(start_utc, occupied_end, off):
        return False, "staff_time_off"
    busy = booked_intervals(
        db, [staff.id], start_utc, occupied_end, exclude_appointment_id=exclude_appointment_id
    ).get(staff.id, [])
    if _overlaps(start_utc, occupied_end, busy):
        return False, "already_booked"
    cal = staff_busy_intervals(
        calendar,
        [staff],
        default_calendar_id=default_calendar_id(settings),
        start=start_utc - timedelta(hours=1),
        end=occupied_end + timedelta(hours=1),
        our_events=lambda ids: _our_event_ids(db, ids),
    ).get(staff.id, [])
    if _overlaps(start_utc, occupied_end, cal):
        return False, "calendar_busy"
    return True, "ok"
