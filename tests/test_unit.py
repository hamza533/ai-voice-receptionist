"""Unit tests: pure logic, no database."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.jobs.handlers import outcome_from_tools
from app.models import ToolCall
from app.services.availability import SlotQuery, compute_slots
from app.services.privacy import mask_phone, normalize_email, phones_match, redact
from app.services.retry import backoff_delay, retry_call
from app.services.timeutil import resolve_date, speak_time

TZ = "Asia/Karachi"  # UTC+5, no DST
MON_9AM = datetime(2025, 11, 24, 4, 0, tzinfo=UTC)  # Monday 09:00 local


def _q(**kw) -> SlotQuery:  # type: ignore[no-untyped-def]
    base = dict(
        service_minutes=45,
        buffer_minutes=10,
        staff=[(1, "Sara"), (2, "Omar")],
        hours={d: [(time(10), time(20))] for d in range(6)},
        holidays=set(),
        busy={},
        tz=TZ,
        step_minutes=15,
        min_lead_minutes=60,
        window_days=30,
    )
    base.update(kw)
    return SlotQuery(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- dates


def test_resolve_tomorrow_and_iso() -> None:
    assert resolve_date("tomorrow", TZ, MON_9AM).date == date(2025, 11, 25)
    assert resolve_date("2025-12-01", TZ, MON_9AM).date == date(2025, 12, 1)


def test_resolve_weekday_and_ambiguous_next() -> None:
    fri = resolve_date("friday", TZ, MON_9AM)
    assert fri.date == date(2025, 11, 28) and not fri.ambiguous
    nxt = resolve_date("next friday", TZ, MON_9AM)
    assert nxt.ambiguous and nxt.date == date(2025, 11, 28)
    assert nxt.alternative == date(2025, 12, 5)


def test_resolve_same_weekday_means_next_week() -> None:
    assert resolve_date("monday", TZ, MON_9AM).date == date(2025, 12, 1)


def test_resolve_uses_business_timezone_not_utc() -> None:
    # 20:30 UTC Monday is already Tuesday 01:30 in Karachi.
    late = datetime(2025, 11, 24, 20, 30, tzinfo=UTC)
    assert resolve_date("today", TZ, late).date == date(2025, 11, 25)


def test_resolve_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        resolve_date("whenever suits", TZ, MON_9AM)


def test_speak_time_in_local_zone() -> None:
    assert speak_time(datetime(2025, 11, 25, 10, 30, tzinfo=UTC), TZ) == (
        "Tuesday 25 November at 3:30 PM"
    )


# ---------------------------------------------------------------- slots


def test_slots_respect_hours_lead_time_and_spacing() -> None:
    slots = compute_slots(
        _q(), date_from=date(2025, 11, 24), date_to=date(2025, 11, 24), now_utc=MON_9AM, limit=10
    )
    assert slots, "expected free slots on an empty day"
    locals_ = [s.start_utc.astimezone(UTC) + timedelta(hours=5) for s in slots]
    assert all(time(10) <= t.time() for t in locals_)
    assert all((t + timedelta(minutes=45)).time() <= time(20) for t in locals_)
    assert len(slots) <= 3  # per-day limit
    gaps = [b.start_utc - a.start_utc for a, b in itertools.pairwise(slots)]
    assert all(g >= timedelta(minutes=60) for g in gaps)


def test_slots_skip_sunday_and_holidays() -> None:
    sun = date(2025, 11, 30)
    assert compute_slots(_q(), date_from=sun, date_to=sun, now_utc=MON_9AM) == []
    tue = date(2025, 11, 25)
    assert compute_slots(_q(holidays={tue}), date_from=tue, date_to=tue, now_utc=MON_9AM) == []


def test_slots_avoid_busy_including_buffer() -> None:
    tue = date(2025, 11, 25)
    whole_day_busy = [
        (datetime(2025, 11, 25, 5, 0, tzinfo=UTC), datetime(2025, 11, 25, 15, 0, tzinfo=UTC))
    ]
    q = _q(busy={1: whole_day_busy}, staff=[(1, "Sara")])
    assert compute_slots(q, date_from=tue, date_to=tue, now_utc=MON_9AM) == []
    # Busy 10:00-14:00 local; with 45 min + 10 buffer, first slot is 14:00.
    morning = [(datetime(2025, 11, 25, 5, 0, tzinfo=UTC), datetime(2025, 11, 25, 9, 0, tzinfo=UTC))]
    q = _q(busy={1: morning}, staff=[(1, "Sara")])
    first = compute_slots(q, date_from=tue, date_to=tue, now_utc=MON_9AM)[0]
    assert first.start_utc == datetime(2025, 11, 25, 9, 0, tzinfo=UTC)


def test_slots_fall_back_to_other_staff() -> None:
    tue = date(2025, 11, 25)
    sara_busy = [
        (datetime(2025, 11, 25, 5, 0, tzinfo=UTC), datetime(2025, 11, 25, 15, 0, tzinfo=UTC))
    ]
    slots = compute_slots(_q(busy={1: sara_busy}), date_from=tue, date_to=tue, now_utc=MON_9AM)
    assert slots and all(s.staff_id == 2 for s in slots)


def test_slots_time_of_day_filter_and_window() -> None:
    tue = date(2025, 11, 25)
    slots = compute_slots(
        _q(), date_from=tue, date_to=tue, now_utc=MON_9AM, after_local_time=time(17)
    )
    assert slots and all((s.start_utc + timedelta(hours=5)).time() >= time(17) for s in slots)
    far = date(2026, 3, 1)
    assert compute_slots(_q(), date_from=far, date_to=far, now_utc=MON_9AM) == []


# ---------------------------------------------------------------- privacy & misc


def test_phone_matching_and_masking() -> None:
    assert phones_match("+92 300 1234567", "03001234567")
    assert not phones_match("+92 300 1234567", "+92 300 7654321")
    assert not phones_match("", "123")
    assert mask_phone("+923001234567") == "•••• 4567"
    assert normalize_email(" Ayesha.K@Example.com ") == "ayesha.k@example.com"
    assert normalize_email("not-an-email") == ""


def test_redact_hides_personal_data() -> None:
    out = redact(
        {
            "customer_name": "Ayesha",
            "phone": "+923001234567",
            "email": "a@example.com",
            "service": "Haircut",
        }
    )
    assert out["customer_name"] == "[redacted]"
    assert out["phone"].endswith("4567") and "300" not in out["phone"]
    assert out["email"] == "a•••@example.com"
    assert out["service"] == "Haircut"


def test_outcome_precedence() -> None:
    def tc(tool: str, status: str = "ok") -> ToolCall:
        return ToolCall(tool=tool, result_status=status)

    assert outcome_from_tools([tc("answer_faq"), tc("book_appointment")], 4) == "booked"
    assert outcome_from_tools([tc("book_appointment", "unavailable")], 4) == "faq_answered"
    assert outcome_from_tools([tc("request_human"), tc("book_appointment")], 4) == (
        "handed_to_human"
    )
    assert outcome_from_tools([], 1) == "abandoned"


def test_retry_call_retries_then_raises() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    assert retry_call(flaky, what="t", attempts=3, sleep=lambda _: None) == "ok"
    with pytest.raises(RuntimeError):
        retry_call(
            lambda: (_ for _ in ()).throw(RuntimeError("x")),
            what="t",
            attempts=2,
            sleep=lambda _: None,
        )
    assert 0 <= backoff_delay(10, base=0.5, cap=8) <= 8
