"""Time-zone helpers. Everything is stored in UTC and spoken in the business time zone."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WEEKDAY_ALIASES = {d[:3]: i for i, d in enumerate(WEEKDAYS)} | {
    d: i for i, d in enumerate(WEEKDAYS)
}
_WEEKDAY_ALIASES |= {"tues": 1, "weds": 2, "thur": 3, "thurs": 3}


_Date = date  # alias: the ResolvedDate.date field shadows the type name


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime; attach the business time zone first")
    return dt.astimezone(UTC)


def to_local(dt: datetime, tz: str) -> datetime:
    return dt.astimezone(ZoneInfo(tz))


def local_today(tz: str, now: datetime | None = None) -> date:
    return to_local(now or utcnow(), tz).date()


# Caller-facing parts of the day (business-local), shared by availability and the waitlist.
TIME_WINDOWS: dict[str, tuple[time | None, time | None]] = {
    "morning": (None, time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), None),
    "any": (None, None),
}


def short_when(dt: datetime, tz: str) -> str:
    """'Tue 25 Nov at 2:30 PM' in the business time zone (for texts)."""
    loc = to_local(dt, tz)
    return f"{loc:%a %d %b} at {loc:%I:%M %p}".replace(" 0", " ")


def speak_time(dt: datetime, tz: str) -> str:
    """'Tuesday 25 November at 3:30 PM' in the business time zone."""
    loc = to_local(dt, tz)
    hour = loc.strftime("%I").lstrip("0") or "12"
    minute = "" if loc.minute == 0 else f":{loc.minute:02d}"
    return f"{loc.strftime('%A')} {loc.day} {loc.strftime('%B')} at {hour}{minute} {loc:%p}"


def speak_date(d: date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')} {d.year}"


@dataclass(frozen=True)
class ResolvedDate:
    date: date
    spoken: str
    ambiguous: bool = False
    alternative: _Date | None = None

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "date": self.date.isoformat(),
            "spoken": self.spoken,
            "ambiguous": self.ambiguous,
        }
        if self.alternative is not None:
            out["alternative"] = self.alternative.isoformat()
            out["alternative_spoken"] = speak_date(self.alternative)
        return out


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Models sometimes send a full timestamp ("2026-11-24T12:00:00"): use its date part.
_ISO_DATETIME = re.compile(r"^(\d{4}-\d{2}-\d{2})[t ]\d{2}:\d{2}")
_IN_N_DAYS = re.compile(r"^in (\d{1,2}) days?$")


def resolve_date(phrase: str, tz: str, now: datetime | None = None) -> ResolvedDate:
    """Resolve an ISO date or a simple relative phrase in the business time zone.

    "next <weekday>" is genuinely ambiguous in English: when it could mean this coming
    one or the one a week later, both are returned and the agent must confirm.
    """
    today = local_today(tz, now)
    p = " ".join(phrase.lower().strip().replace(",", " ").split())

    if m := _ISO_DATETIME.match(p):
        p = m.group(1)
    if _ISO.match(p):
        d = date.fromisoformat(p)
        return ResolvedDate(d, speak_date(d))
    if p in {"today", "now", "this afternoon", "this evening", "this morning"}:
        return ResolvedDate(today, speak_date(today))
    if p in {"tomorrow", "tmrw", "tomorrow morning", "tomorrow afternoon"}:
        d = today + timedelta(days=1)
        return ResolvedDate(d, speak_date(d))
    if p in {"day after tomorrow", "the day after tomorrow"}:
        d = today + timedelta(days=2)
        return ResolvedDate(d, speak_date(d))
    if p in {"next week", "early next week"}:
        d = today + timedelta(days=7 - today.weekday())
        return ResolvedDate(d, speak_date(d))
    if m := _IN_N_DAYS.match(p):
        d = today + timedelta(days=int(m.group(1)))
        return ResolvedDate(d, speak_date(d))

    words = p.split()
    prefix = words[0] if len(words) == 2 else ""
    name = words[-1]
    if name in _WEEKDAY_ALIASES and (len(words) == 1 or prefix in {"this", "next", "coming"}):
        target = _WEEKDAY_ALIASES[name]
        ahead = (target - today.weekday()) % 7
        if ahead == 0:
            ahead = 7  # "Friday" said on a Friday means the next one
        first = today + timedelta(days=ahead)
        if prefix == "next":
            later = first + timedelta(days=7)
            # If the coming one is still in the current week, people may mean either.
            same_week = first.isocalendar()[1] == today.isocalendar()[1]
            if same_week:
                return ResolvedDate(first, speak_date(first), ambiguous=True, alternative=later)
        return ResolvedDate(first, speak_date(first))

    raise ValueError(f"could not understand date '{phrase}'; ask the caller for a specific date")
