"""Integration tests for staff schedules, time off, texts, reminders, the waitlist, the
"value booked" figures and Google Calendar connect (real Postgres)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import func, select

from app.jobs import handlers
from app.models import (
    Appointment,
    Integration,
    Job,
    SmsMessage,
    Staff,
    StaffShift,
    TimeOff,
    WaitlistEntry,
)
from app.services import sms as sms_svc
from app.services.tools import run_tool
from tests.conftest import NOW, login
from tests.test_booking import _book, _call, _ctx, _offer

pytestmark = pytest.mark.integration

TZ = ZoneInfo("Asia/Karachi")
TUESDAY = datetime(2025, 11, 25).date()


@pytest.fixture
def frozen(monkeypatch):  # type: ignore[no-untyped-def]
    """Jobs, reminders and text replies read the clock; pin it to the tests' NOW."""
    clock = {"now": NOW}
    for target in (
        "app.services.booking.utcnow",
        "app.jobs.handlers.utcnow",
        "app.api.sms_api.utcnow",
        "app.api.waitlist_api.utcnow",
        "app.api.settings_api.utcnow",
    ):
        monkeypatch.setattr(target, lambda: clock["now"])
    return clock


def _staff(db, name: str) -> Staff:  # type: ignore[no-untyped-def]
    return db.scalar(select(Staff).where(Staff.name == name))


def _local(slot: dict) -> datetime:
    return datetime.fromisoformat(slot["start_utc"]).astimezone(TZ)


def _run_jobs(db, settings, kind: str) -> int:  # type: ignore[no-untyped-def]
    """Run every queued job of one kind through its handler (as the worker would)."""
    jobs = list(db.scalars(select(Job).where(Job.kind == kind, Job.status == "queued")))
    for job in jobs:
        handlers.HANDLERS[kind](db, settings, dict(job.payload))
        job.status = "done"
    db.commit()
    return len(jobs)


# ---------------------------------------------------------------- schedules & time off


def test_staff_shifts_limit_when_they_are_offered(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    omar = _staff(db, "Omar")
    omar.shifts = [StaffShift(weekday=d, start_time=time(12), end_time=time(18)) for d in (2, 3)]
    db.commit()
    ctx = _ctx(db, settings, calendar, _call(db))
    slots = _offer(ctx, service="Beard trim", staff="Omar", when="tomorrow")
    assert slots, "next openings are offered when the requested day has no shift"
    for s in slots:
        local = _local(s)
        assert local.weekday() in (2, 3)
        assert time(12) <= local.time() and (local + timedelta(minutes=20)).time() <= time(18)


def test_time_off_and_weekly_breaks_block_slots(
    client, db, settings, calendar, admin, frozen
) -> None:  # type: ignore[no-untyped-def]
    headers = login(client, admin["email"], admin["password"])
    sara = _staff(db, "Sara")
    r = client.post(
        "/api/settings/time-off",
        headers=headers,
        json={
            "staff_id": sara.id,
            "kind": "weekly",
            "weekday": 1,
            "start_time": "13:00",
            "end_time": "15:00",
            "label": "Lunch",
        },
    )
    assert r.status_code == 201, r.text
    ctx = _ctx(db, settings, calendar, _call(db))
    slots = _offer(ctx, service="Hair colour", when="tomorrow", time_of_day="afternoon")
    for s in slots:
        start = _local(s)
        if start.date() == TUESDAY:  # 2-hour colour must not overlap 13:00-15:00
            end = (start + timedelta(minutes=120)).time()
            assert end <= time(13) or start.time() >= time(15)

    r = client.post(
        "/api/settings/time-off",
        headers=headers,
        json={
            "staff_id": sara.id,
            "kind": "once",
            "start_local": "2025-11-25T00:00",
            "end_local": "2025-11-26T00:00",
            "label": "Day off",
        },
    )
    assert r.status_code == 201, r.text
    assert datetime.fromisoformat(r.json()["start_utc"]).astimezone(TZ).hour == 0
    later = _offer(ctx, service="Hair colour", when="tomorrow")
    assert all(_local(s).date() != TUESDAY for s in later)
    listed = client.get(f"/api/settings/time-off?staff_id={sara.id}").json()
    assert {t["kind"] for t in listed} == {"weekly", "once"}


def test_time_off_added_after_an_offer_blocks_the_booking(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    slot = _offer(ctx, staff="Sara")[0]
    start = datetime.fromisoformat(slot["start_utc"])
    db.add(
        TimeOff(
            staff_id=_staff(db, "Sara").id,
            kind="once",
            start_utc=start - timedelta(minutes=30),
            end_utc=start + timedelta(hours=2),
            label="Doctor",
        )
    )
    db.commit()
    res = _book(ctx, slot)
    assert res.status == "unavailable"
    assert db.scalar(select(func.count(Appointment.id))) == 0


def test_shift_api_validates_and_returns_shifts(client, db, admin) -> None:  # type: ignore[no-untyped-def]
    headers = login(client, admin["email"], admin["password"])
    omar = _staff(db, "Omar")
    overlap = [
        {"weekday": 1, "start_time": "10:00", "end_time": "14:00"},
        {"weekday": 1, "start_time": "13:00", "end_time": "18:00"},
    ]
    assert (
        client.put(
            f"/api/settings/staff/{omar.id}/shifts", headers=headers, json=overlap
        ).status_code
        == 422
    )
    ok = [
        {"weekday": 1, "start_time": "10:00", "end_time": "13:00"},
        {"weekday": 1, "start_time": "14:00", "end_time": "19:00"},
    ]
    r = client.put(f"/api/settings/staff/{omar.id}/shifts", headers=headers, json=ok)
    assert r.status_code == 200, r.text
    staff = {s["name"]: s for s in client.get("/api/settings/staff").json()}
    assert len(staff["Omar"]["shifts"]) == 2 and staff["Sara"]["shifts"] == []
    cleared = client.put(f"/api/settings/staff/{omar.id}/shifts", headers=headers, json=[])
    assert cleared.json()["shifts"] == []


# ---------------------------------------------------------------- texts & reminders


def test_booking_queues_confirmation_text_and_reminder(db, settings, calendar, frozen) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    assert _book(ctx, _offer(ctx, when="wednesday")[0]).status == "ok"
    appt = db.scalar(select(Appointment))
    reminder = db.scalar(select(Job).where(Job.kind == "send_reminder"))
    assert reminder is not None and reminder.run_at == appt.start_utc - timedelta(hours=24)
    assert _run_jobs(db, settings, "send_booking_sms") == 1
    sent = db.scalar(select(SmsMessage).where(SmsMessage.kind == "customer_booked"))
    assert sent.status == "skipped" and "You're booked" in sent.body and "Reply C" in sent.body

    # Moved since: the old reminder is skipped, the new time gets its own.
    stale = {
        "appointment_id": str(appt.id),
        "start_utc": (appt.start_utc - timedelta(days=1)).isoformat(),
    }
    handlers.handle_send_reminder(db, settings, stale)
    assert db.scalar(select(func.count()).where(SmsMessage.kind == "customer_reminder")) == 0
    handlers.handle_send_reminder(
        db, settings, {"appointment_id": str(appt.id), "start_utc": appt.start_utc.isoformat()}
    )
    assert db.scalar(select(func.count()).where(SmsMessage.kind == "customer_reminder")) == 1


def test_send_sms_posts_to_twilio_once(db, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok")
    monkeypatch.setattr(settings, "twilio_from_number", "+15550001111")
    monkeypatch.setattr(settings, "sms_default_country_code", "+92")
    seen: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"sid": "SM1"})

    transport = httpx.MockTransport(reply)
    for _ in range(2):
        status = sms_svc.send_sms(
            db, settings, key="k1", to="0300 1112233", body="Hi", kind="test", transport=transport
        )
        assert status == "sent"
    assert len(seen) == 1
    form = parse_qs(seen[0].content.decode())
    assert form["To"] == ["+923001112233"] and form["From"] == ["+15550001111"]


@pytest.fixture
def sms_on(monkeypatch, settings):  # type: ignore[no-untyped-def]
    from app.config import get_settings

    monkeypatch.setattr(
        sms_svc,
        "DEFAULT_TRANSPORT",
        httpx.MockTransport(lambda request: httpx.Response(201, json={"sid": "SM1"})),
    )
    for k, v in {
        "TWILIO_ACCOUNT_SID": "AC123",
        "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_FROM_NUMBER": "+15550001111",
        "PUBLIC_URL": "https://salon.example.com",
    }.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def _text(client, sms_on, phone: str, body: str, signature: str | None = None):  # type: ignore[no-untyped-def]
    params = {"From": phone, "Body": body, "MessageSid": "SM9"}
    url = "https://salon.example.com/api/sms/inbound"
    sig = signature if signature is not None else sms_svc.twilio_signature(url, params, "tok")
    return client.post(
        "/api/sms/inbound",
        content=httpx.QueryParams(params).__str__(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "X-Twilio-Signature": sig},
    )


def test_texting_c_cancels_the_only_upcoming_booking(client, db, calendar, sms_on, frozen) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, sms_on, calendar, _call(db))
    assert _book(ctx, _offer(ctx)[0]).status == "ok"
    assert _text(client, sms_on, "+923001112233", "C", signature="forged").status_code == 403
    r = _text(client, sms_on, "+923001112233", " c ")
    assert r.status_code == 200 and "is cancelled" in r.text
    db.expire_all()
    assert db.scalar(select(Appointment)).status == "cancelled"
    assert "reply C to cancel" in _text(client, sms_on, "+923001112233", "hello").text
    # The forged request was refused before anything was recorded.
    assert db.scalar(select(func.count()).where(SmsMessage.direction == "in")) == 2


# ---------------------------------------------------------------- waitlist


def test_cancellation_is_offered_to_the_waitlist_and_taken_by_text(  # type: ignore[no-untyped-def]
    client, db, calendar, sms_on, frozen
) -> None:
    settings = sms_on
    a = _ctx(db, settings, calendar, _call(db, number="+923001111111"))
    slot = _offer(a, service="Hair colour", staff="Sara")[0]
    assert _book(a, slot, service="Hair colour").status == "ok"

    b = _ctx(db, settings, calendar, _call(db, number="+923002222222"))
    joined = run_tool(
        b,
        "join_waitlist",
        {"service": "Hair colour", "date": "tomorrow", "name": "Bilal Ahmed"},
    )
    assert joined.status == "ok", joined.message
    assert "text" in joined.message

    cancel = run_tool(
        a,
        "cancel_appointment",
        {"contact": "ayesha.k@example.com", "date": "tomorrow", "caller_confirmed": True},
    )
    assert cancel.status == "ok"
    assert _run_jobs(db, settings, "waitlist_match") == 1
    entry = db.scalar(select(WaitlistEntry))
    assert entry.status == "offered"
    assert entry.offer_start_utc == datetime.fromisoformat(slot["start_utc"])
    assert _run_jobs(db, settings, "send_waitlist_offer") == 1
    offer = db.scalar(select(SmsMessage).where(SmsMessage.kind == "waitlist_offer"))
    assert "Reply YES" in offer.body and offer.status == "sent"

    r = _text(client, settings, "+92 300 2222222", "Yes")
    assert r.status_code == 200 and "booked!" in r.text
    db.expire_all()
    booked = db.scalar(select(Appointment).where(Appointment.status == "booked"))
    assert booked.customer_name == "Bilal Ahmed"
    assert db.scalar(select(WaitlistEntry)).status == "booked"


def test_expired_hold_passes_the_time_to_the_next_person(db, settings, calendar, frozen) -> None:  # type: ignore[no-untyped-def]
    from app.services import waitlist

    sara = _staff(db, "Sara")
    service = next(s for s in sara.services if s.name == "Haircut")
    first, _ = waitlist.add_entry(db, name="B", phone="+923002222222", service=service, day=TUESDAY)
    second, _ = waitlist.add_entry(
        db, name="C", phone="+923003333333", service=service, day=TUESDAY
    )
    start = datetime(2025, 11, 25, 11, 0, tzinfo=TZ)
    offered = waitlist.match_freed_slot(
        db, calendar, settings, staff_id=sara.id, start_utc=start, now=NOW
    )
    assert offered is not None and offered.id == first.id

    frozen["now"] = NOW + timedelta(minutes=31)
    job = db.scalar(select(Job).where(Job.kind == "waitlist_expire"))
    handlers.handle_waitlist_expire(db, settings, dict(job.payload))
    db.expire_all()
    assert db.get(WaitlistEntry, first.id).status == "waiting"
    assert db.get(WaitlistEntry, second.id).status == "offered"
    # The first person isn't offered the same time again.
    assert waitlist.slot_key(sara.id, start) in db.get(WaitlistEntry, first.id).offered_slots


def test_waitlist_dashboard_add_book_and_remove(client, db, admin, calendar, frozen) -> None:  # type: ignore[no-untyped-def]
    headers = login(client, admin["email"], admin["password"])
    sara = _staff(db, "Sara")
    haircut = next(s for s in sara.services if s.name == "Haircut")
    body = {"name": "Dana", "phone": "+923004444444", "service_id": haircut.id, "day": "2025-11-25"}
    r = client.post("/api/waitlist", headers=headers, json=body)
    assert r.status_code == 201, r.text
    entry_id = r.json()["id"]
    assert client.post("/api/waitlist", headers=headers, json=body).json()["id"] == entry_id
    assert client.post(f"/api/waitlist/{entry_id}/book", headers=headers).status_code == 409

    from app.config import get_settings
    from app.services import waitlist

    waitlist.match_freed_slot(
        db,
        calendar,
        get_settings(),
        staff_id=sara.id,
        start_utc=datetime(2025, 11, 25, 11, 0, tzinfo=TZ),
        now=NOW,
    )
    listed = client.get("/api/waitlist").json()
    assert listed[0]["status"] == "offered" and listed[0]["offer_staff"] == "Sara"
    booked = client.post(f"/api/waitlist/{entry_id}/book", headers=headers)
    assert booked.status_code == 200, booked.text
    assert client.get("/api/waitlist").json() == []
    assert client.delete(f"/api/waitlist/{entry_id}", headers=headers).status_code == 204


# ---------------------------------------------------------------- overview & setup


def test_overview_reports_value_booked_by_ava(client, db, settings, calendar, admin) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    assert _book(ctx, _offer(ctx)[0]).status == "ok"
    login(client, admin["email"], admin["password"])
    data = client.get("/api/stats/overview?days=7").json()
    assert data["currency"] == "PKR"
    assert data["booked_value"] == 2500.0 and data["booked_value_count"] == 1
    assert "after_hours_calls" in data and "after_hours_value" in data


def test_setup_can_be_completed(client, db, admin) -> None:  # type: ignore[no-untyped-def]
    from app.models import BusinessConfig

    headers = login(client, admin["email"], admin["password"])
    db.get(BusinessConfig, 1).setup_completed = False
    db.commit()
    assert client.get("/api/settings/business").json()["setup_completed"] is False
    r = client.post("/api/settings/setup/complete", headers=headers)
    assert r.status_code == 200 and r.json()["setup_completed"] is True


# ---------------------------------------------------------------- Google Calendar connect


def test_google_connect_stores_an_encrypted_refresh_token(client, db, admin, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.config import get_settings
    from app.services import calendar as cal
    from app.services import google_oauth
    from app.services.crypto import decrypt

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("PUBLIC_URL", "https://salon.example.com")
    get_settings.cache_clear()
    cal.invalidate_connection_cache()
    monkeypatch.setattr(
        google_oauth,
        "exchange_code",
        lambda s, code: {"refresh_token": "rt-1", "access_token": "at"},
    )
    monkeypatch.setattr(google_oauth, "account_email", lambda token: "owner@gmail.com")
    monkeypatch.setattr(google_oauth, "revoke", lambda token: None)
    headers = login(client, admin["email"], admin["password"])

    start = client.get("/api/integrations/google/start", follow_redirects=False)
    assert start.status_code == 302
    url = urlparse(start.headers["location"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert query["redirect_uri"] == ["https://salon.example.com/api/integrations/google/callback"]
    state = query["state"][0]

    ok = client.get(
        f"/api/integrations/google/callback?code=x&state={state}", follow_redirects=False
    )
    assert ok.headers["location"].endswith("calendar=connected")
    row = db.scalar(select(Integration))
    assert (
        row.refresh_token_enc != "rt-1" and decrypt(get_settings(), row.refresh_token_enc) == "rt-1"
    )
    status = client.get("/api/integrations").json()["google"]
    assert status["connected"] and status["account_email"] == "owner@gmail.com"
    assert status["calendar_id"] == "owner@gmail.com"

    client.get("/api/integrations/google/start", follow_redirects=False)
    forged = client.get(
        "/api/integrations/google/callback?code=x&state=forged", follow_redirects=False
    )
    assert forged.headers["location"].endswith("calendar=error")

    assert client.delete("/api/integrations/google", headers=headers).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count(Integration.id))) == 0
    get_settings.cache_clear()
    cal.invalidate_connection_cache()


# ---------------------------------------------------------------- review fixes


def test_resaving_a_shift_with_the_same_start_works(client, db, admin) -> None:  # type: ignore[no-untyped-def]
    headers = login(client, admin["email"], admin["password"])
    sara = _staff(db, "Sara")
    url = f"/api/settings/staff/{sara.id}/shifts"
    first = [{"weekday": 0, "start_time": "10:00", "end_time": "18:00"}]
    assert client.put(url, headers=headers, json=first).status_code == 200
    changed = [{"weekday": 0, "start_time": "10:00", "end_time": "17:00"}]
    r = client.put(url, headers=headers, json=changed)
    assert r.status_code == 200, r.text
    assert r.json()["shifts"] == [{"weekday": 0, "start_time": "10:00:00", "end_time": "17:00:00"}]


def test_a_freed_time_is_offered_to_one_person_at_a_time(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    from app.services import waitlist

    sara = _staff(db, "Sara")
    haircut = next(s for s in sara.services if s.name == "Haircut")
    waitlist.add_entry(db, name="B", phone="+923002222222", service=haircut, day=TUESDAY)
    waitlist.add_entry(db, name="C", phone="+923003333333", service=haircut, day=TUESDAY)
    start = datetime(2025, 11, 25, 11, 0, tzinfo=TZ)
    first = waitlist.match_freed_slot(
        db, calendar, settings, staff_id=sara.id, start_utc=start, now=NOW
    )
    again = waitlist.match_freed_slot(
        db, calendar, settings, staff_id=sara.id, start_utc=start, now=NOW
    )
    assert first is not None and again is None
    assert db.scalar(select(func.count()).where(WaitlistEntry.status == "offered")) == 1


def test_booking_another_service_keeps_the_waitlist_entry(db, settings, calendar, frozen) -> None:  # type: ignore[no-untyped-def]
    from app.services import waitlist

    sara = _staff(db, "Sara")
    colour = next(s for s in sara.services if s.name == "Hair colour")
    entry, _ = waitlist.add_entry(
        db, name="Ayesha", phone="+923001112233", service=colour, day=TUESDAY
    )
    ctx = _ctx(db, settings, calendar, _call(db))  # same caller number
    assert _book(ctx, _offer(ctx, staff="Sara")[0]).status == "ok"  # a Haircut on Tuesday
    db.expire_all()
    assert db.get(WaitlistEntry, entry.id).status == "waiting"


def test_sweep_offers_times_freed_without_a_cancellation(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    from app.services import waitlist

    sara = _staff(db, "Sara")
    haircut = next(s for s in sara.services if s.name == "Haircut")
    off = TimeOff(
        staff_id=sara.id,
        kind="once",
        start_utc=datetime(2025, 11, 25, 0, 0, tzinfo=TZ),
        end_utc=datetime(2025, 11, 26, 0, 0, tzinfo=TZ),
    )
    db.add(off)
    db.commit()
    entry, _ = waitlist.add_entry(
        db, name="B", phone="+923002222222", service=haircut, day=TUESDAY, staff=sara
    )
    assert waitlist.sweep(db, calendar, settings, NOW) == 0  # Sara is off all Tuesday
    db.delete(off)
    db.commit()
    assert waitlist.sweep(db, calendar, settings, NOW) == 1
    db.expire_all()
    offered = db.get(WaitlistEntry, entry.id)
    assert offered.status == "offered" and offered.offer_staff_id == sara.id
