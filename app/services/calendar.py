"""Google Calendar integration behind a small interface.

- Events created by the receptionist get a deterministic id derived from the booking's
  idempotency key, so a retried request can never create a second event.
- Each event carries `extendedProperties.private.staff_id`. On a shared business
  calendar, an event tagged with a staff id blocks only that person; an untagged event
  (e.g. "Salon closed for training") blocks everyone.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol

from app.config import Settings, get_settings
from app.services.retry import retry_call

if TYPE_CHECKING:
    from app.models import Staff

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


@dataclass(frozen=True)
class BusyEvent:
    id: str
    start: datetime
    end: datetime
    staff_id: int | None


class CalendarClient(Protocol):
    name: str

    def list_busy(self, calendar_id: str, start: datetime, end: datetime) -> list[BusyEvent]: ...

    def upsert_event(
        self,
        calendar_id: str,
        event_id: str,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        staff_id: int,
        timezone: str,
    ) -> str: ...

    def delete_event(self, calendar_id: str, event_id: str) -> None: ...


def event_id_for(idempotency_key: str) -> str:
    """Google event ids allow [a-v0-9]{5,1024}; hex digits are a subset."""
    return "rcp" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:40]


class LocalCalendar:
    """Used when Google credentials are not configured (local dev, tests, CI).

    Bookings still work: the database is the source of truth for receptionist-made
    appointments, so slots stay correct. Only external calendar events are unknown.
    """

    name = "local"

    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.external: list[tuple[str, BusyEvent]] = []

    def list_busy(self, calendar_id: str, start: datetime, end: datetime) -> list[BusyEvent]:
        return [
            e for cal, e in self.external if cal == calendar_id and e.start < end and e.end > start
        ]

    def upsert_event(
        self,
        calendar_id: str,
        event_id: str,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        staff_id: int,
        timezone: str,
    ) -> str:
        self.events[event_id] = {
            "calendar_id": calendar_id,
            "summary": summary,
            "start": start,
            "end": end,
            "staff_id": staff_id,
        }
        return event_id

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        self.events.pop(event_id, None)


class GoogleCalendar:
    name = "google"

    def __init__(self, service_account_json: str, timeout_s: float = 10.0) -> None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._timeout = timeout_s

    def list_busy(self, calendar_id: str, start: datetime, end: datetime) -> list[BusyEvent]:
        out: list[BusyEvent] = []
        page_token: str | None = None
        while True:
            req = self._svc.events().list(
                calendarId=calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
                maxResults=250,
            )
            resp = retry_call(req.execute, what="calendar.list")
            for ev in resp.get("items", []):
                if ev.get("status") == "cancelled" or ev.get("transparency") == "transparent":
                    continue
                s, e = ev.get("start", {}), ev.get("end", {})
                if "dateTime" not in s:  # all-day event: treat as blocking the whole day
                    from datetime import date, time
                    from zoneinfo import ZoneInfo

                    tz = ZoneInfo(s.get("timeZone") or "UTC")
                    s_dt = datetime.combine(date.fromisoformat(s["date"]), time.min, tzinfo=tz)
                    e_dt = datetime.combine(date.fromisoformat(e["date"]), time.min, tzinfo=tz)
                else:
                    s_dt = datetime.fromisoformat(s["dateTime"])
                    e_dt = datetime.fromisoformat(e["dateTime"])
                staff = ev.get("extendedProperties", {}).get("private", {}).get("staff_id")
                out.append(
                    BusyEvent(
                        ev["id"], s_dt, e_dt, int(staff) if staff and staff.isdigit() else None
                    )
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                return out

    def upsert_event(
        self,
        calendar_id: str,
        event_id: str,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        staff_id: int,
        timezone: str,
    ) -> str:
        from googleapiclient.errors import HttpError

        body = {
            "id": event_id,
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone},
            "extendedProperties": {"private": {"staff_id": str(staff_id), "source": "receptly"}},
            "status": "confirmed",
        }

        def _insert() -> str:
            try:
                self._svc.events().insert(calendarId=calendar_id, body=body).execute()
            except HttpError as exc:
                if exc.resp.status == 409:  # already exists (retry or reschedule): update it
                    self._svc.events().update(
                        calendarId=calendar_id, eventId=event_id, body=body
                    ).execute()
                else:
                    raise
            return event_id

        return retry_call(_insert, what="calendar.upsert")

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        from googleapiclient.errors import HttpError

        def _delete() -> None:
            try:
                self._svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            except HttpError as exc:
                if exc.resp.status not in (404, 410):  # already gone is fine
                    raise

        retry_call(_delete, what="calendar.delete")


_local_singleton = LocalCalendar()


@lru_cache
def _google(service_account_json: str) -> GoogleCalendar:
    return GoogleCalendar(service_account_json)


def get_calendar(settings: Settings | None = None) -> CalendarClient:
    settings = settings or get_settings()
    if settings.calendar_enabled:
        return _google(settings.google_service_account_json)
    return _local_singleton


def calendar_for_staff(staff: Staff, default_calendar_id: str) -> str:
    return staff.calendar_id or default_calendar_id or "primary"


def staff_busy_intervals(
    calendar: CalendarClient,
    staff: Sequence[Staff],
    *,
    default_calendar_id: str,
    start: datetime,
    end: datetime,
    ignore_event_ids: Iterable[str] = (),
) -> dict[int, list[tuple[datetime, datetime]]]:
    """Busy intervals per staff member from their calendars (DB bookings excluded)."""
    ignore = set(ignore_event_ids)
    by_calendar: dict[str, list[Staff]] = {}
    for s in staff:
        by_calendar.setdefault(calendar_for_staff(s, default_calendar_id), []).append(s)

    busy: dict[int, list[tuple[datetime, datetime]]] = {}
    for cal_id, members in by_calendar.items():
        events = calendar.list_busy(cal_id, start, end)
        shared = len(members) > 1 or not members[0].calendar_id
        for ev in events:
            if ev.id in ignore:
                continue
            for s in members:
                if shared and ev.staff_id is not None and ev.staff_id != s.id:
                    continue
                busy.setdefault(s.id, []).append((ev.start, ev.end))
    return busy
