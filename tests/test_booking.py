"""Integration tests for the receptionist tools and booking rules (real Postgres)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Appointment, Call, Job, Message, ToolCall
from app.services import booking as booking_svc
from app.services.calendar import LocalCalendar
from app.services.tools import ToolContext, run_tool
from tests.conftest import NOW

pytestmark = pytest.mark.integration


def _call(db, channel: str = "phone", number: str = "+923001112233") -> Call:  # type: ignore[no-untyped-def]
    call = Call(
        channel=channel, room_name="t", caller_number=number, started_at=NOW, status="active"
    )
    db.add(call)
    db.commit()
    return call


def _ctx(db, settings, calendar, call=None) -> ToolContext:  # type: ignore[no-untyped-def]
    return ToolContext(db, calendar, settings, call, now_utc=NOW)


def _offer(ctx: ToolContext, service: str = "Haircut", when: str = "tomorrow", **kw) -> list[dict]:  # type: ignore[no-untyped-def]
    res = run_tool(ctx, "check_availability", {"service": service, "date_from": when, **kw})
    assert res.status == "ok", res.message
    return res.data["slots"]


def _book(ctx: ToolContext, slot: dict, **kw):  # type: ignore[no-untyped-def]
    args = {
        "slot_id": slot["slot_id"],
        "service": "Haircut",
        "customer_name": "Ayesha Khan",
        "email": "ayesha.k@example.com",
        "caller_confirmed": True,
    }
    args.update(kw)
    return run_tool(ctx, "book_appointment", args)


def test_business_info_and_faq(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar)
    info = run_tool(ctx, "get_business_info", {"topic": "all"})
    assert info.status == "ok"
    assert info.data["name"] == "Luma Hair Studio"
    assert info.data["opening_hours"]["Sunday"] == "closed"
    assert any(s["name"] == "Hair colour" for s in info.data["services"])
    faq = run_tool(ctx, "answer_faq", {"question": "where can I park my car?"})
    assert faq.status == "ok" and "parking" in faq.data["answer"].lower()
    miss = run_tool(ctx, "answer_faq", {"question": "do you repair laptops?"})
    assert miss.status == "not_found"


def test_book_flow_requires_offered_slot_and_confirmation(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    call = _call(db)
    ctx = _ctx(db, settings, calendar, call)
    # A made-up slot is refused: the agent cannot invent times.
    invented = run_tool(
        ctx,
        "book_appointment",
        {
            "slot_id": "1:20251125T0700Z",
            "service": "Haircut",
            "customer_name": "Ayesha Khan",
            "caller_confirmed": True,
        },
    )
    assert invented.status == "invalid"
    slots = _offer(ctx)
    unconfirmed = _book(ctx, slots[0], caller_confirmed=False)
    assert unconfirmed.status == "needs_confirmation"
    assert db.scalar(select(func.count(Appointment.id))) == 0
    done = _book(ctx, slots[0])
    assert done.status == "ok", done.message
    appt = db.scalar(select(Appointment))
    assert appt.status == "booked" and appt.call_id == call.id
    assert appt.calendar_event_id in calendar.events
    assert appt.phone == "+923001112233"  # caller id used when no phone given
    # Confirmation email queued, once.
    assert db.scalar(select(func.count(Job.id)).where(Job.kind == "send_booking_email")) == 1
    # Tool calls recorded with personal data redacted.
    tc = db.scalar(
        select(ToolCall).where(ToolCall.tool == "book_appointment", ToolCall.result_status == "ok")
    )
    assert tc.args["customer_name"] == "[redacted]" and "ayesha" not in str(tc.args)


def test_booking_is_idempotent(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    call = _call(db)
    ctx = _ctx(db, settings, calendar, call)
    slot = _offer(ctx)[0]
    first = _book(ctx, slot)
    again = _book(ctx, slot)
    assert first.status == again.status == "ok"
    assert again.data["already_existed"] is True
    assert db.scalar(select(func.count(Appointment.id))) == 1
    assert len(calendar.events) == 1


def test_offered_slot_taken_by_someone_else_is_refused(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    c1, c2 = _call(db, number="+923001111111"), _call(db, number="+923002222222")
    ctx1, ctx2 = _ctx(db, settings, calendar, c1), _ctx(db, settings, calendar, c2)
    s1 = _offer(ctx1, staff="Sara")[0]
    s2 = _offer(ctx2, staff="Sara")[0]
    assert s1["slot_id"] == s2["slot_id"]
    assert _book(ctx1, s1).status == "ok"
    second = _book(ctx2, s2, customer_name="Bilal Ahmed", email="bilal@example.com")
    assert second.status == "unavailable"
    assert db.scalar(select(func.count(Appointment.id))) == 1


def test_concurrent_bookings_produce_one_appointment(db, settings) -> None:  # type: ignore[no-untyped-def]
    """Two callers confirm the same slot at the same moment: exactly one booking."""
    calendar = LocalCalendar()
    calls = [_call(db, number=f"+92300000000{i}") for i in range(2)]
    ctx0 = _ctx(db, settings, calendar, calls[0])
    slot = _offer(ctx0, staff="Sara")[0]
    staff_id = int(slot["slot_id"].split(":")[0])
    start = datetime.fromisoformat(slot["start_utc"])
    barrier = threading.Barrier(2)
    results: list[str] = []

    def attempt(i: int) -> None:
        with SessionLocal() as s:
            barrier.wait()
            try:
                booking_svc.book(
                    s,
                    calendar,
                    settings,
                    booking_svc.BookingRequest(
                        service_id=1,
                        staff_id=staff_id,
                        start_utc=start,
                        customer_name=f"Caller {i}",
                        phone=f"+92300000000{i}",
                        call_id=calls[i].id,
                    ),
                    now_utc=NOW,
                )
                results.append("ok")
            except booking_svc.BookingError as exc:
                results.append(exc.code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "slot_unavailable"]
    db.expire_all()
    assert db.scalar(select(func.count(Appointment.id))) == 1


def test_unique_index_blocks_double_booking_even_without_lock(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy.exc import IntegrityError

    start = datetime(2025, 11, 25, 6, 0, tzinfo=UTC)
    for i in range(2):
        db.add(
            Appointment(
                service_id=1,
                staff_id=1,
                start_utc=start,
                end_utc=start + timedelta(minutes=45),
                customer_name=f"X{i}",
                phone="+923000000000",
                status="booked",
                idempotency_key=f"k{i}",
            )
        )
        if i == 0:
            db.commit()
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_reschedule_and_cancel_need_matching_contact(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    call = _call(db)
    ctx = _ctx(db, settings, calendar, call)
    slot = _offer(ctx, when="tomorrow")[0]
    assert _book(ctx, slot).status == "ok"

    # Wrong caller: different phone and email -> nothing found, nothing revealed.
    intruder = _ctx(db, settings, calendar, _call(db, number="+923009999999"))
    for tool in ("cancel_appointment", "reschedule_appointment"):
        args = {"contact": "+923009999999", "date": "tomorrow", "caller_confirmed": True}
        if tool == "reschedule_appointment":
            args["new_slot_id"] = slot["slot_id"]
        res = run_tool(intruder, tool, args)
        assert res.status == "not_found"
        assert "Ayesha" not in res.message and not res.data
    res = run_tool(
        intruder,
        "cancel_appointment",
        {"contact": "someone@else.com", "date": "tomorrow", "caller_confirmed": True},
    )
    assert res.status == "not_found"
    assert db.scalar(select(Appointment)).status == "booked"

    # Right caller: read-back first, then reschedule.
    new_slot = _offer(ctx, when="wednesday")[0]
    preview = run_tool(
        ctx,
        "reschedule_appointment",
        {"contact": "ayesha.k@example.com", "date": "tomorrow", "new_slot_id": new_slot["slot_id"]},
    )
    assert preview.status == "needs_confirmation"
    moved = run_tool(
        ctx,
        "reschedule_appointment",
        {
            "contact": "AYESHA.K@example.com",
            "date": "tomorrow",
            "new_slot_id": new_slot["slot_id"],
            "caller_confirmed": True,
        },
    )
    assert moved.status == "ok", moved.message
    appt = db.scalar(select(Appointment))
    db.refresh(appt)
    assert appt.status == "rescheduled"
    assert appt.start_utc == datetime.fromisoformat(new_slot["start_utc"])
    assert calendar.events[appt.calendar_event_id]["start"] == appt.start_utc

    cancelled = run_tool(
        ctx,
        "cancel_appointment",
        {"contact": "+92 300 1112233", "date": "wednesday", "caller_confirmed": True},
    )
    assert cancelled.status == "ok"
    db.refresh(appt)
    assert appt.status == "cancelled"
    assert appt.calendar_event_id not in calendar.events


def test_fully_booked_day_offers_next_openings(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    from app.models import Holiday

    db.add(Holiday(date=datetime(2025, 11, 25).date(), label="Training day"))
    db.commit()
    ctx = _ctx(db, settings, calendar, _call(db))
    res = run_tool(
        ctx,
        "check_availability",
        {"service": "Haircut", "date_from": "2025-11-25", "date_to": "2025-11-25"},
    )
    assert res.status == "ok"
    assert all(not s["start_local"].startswith("2025-11-25") for s in res.data["slots"])
    assert "Nothing free on the requested dates" in res.message


def test_out_of_hours_and_unknown_inputs(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    late = run_tool(
        ctx,
        "check_availability",
        {"service": "Hair colour", "date_from": "tomorrow", "time_of_day": "evening"},
    )
    # 120-minute colour cannot start after 18:00 and must end by 20:00.
    for s in late.data.get("slots", []):
        hh = int(s["start_local"][11:13])
        assert hh <= 18
    bad = run_tool(ctx, "check_availability", {"service": "Tattoo", "date_from": "tomorrow"})
    assert bad.status == "invalid" and "Haircut" in bad.data["services"]
    wrong_staff = run_tool(
        ctx,
        "check_availability",
        {"service": "Beard trim", "date_from": "tomorrow", "staff": "Sara"},
    )
    assert wrong_staff.status == "invalid"
    junk = run_tool(ctx, "book_appointment", {"slot_id": "nope"})
    assert junk.status == "invalid"


def test_ambiguous_next_friday_is_flagged(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    res = run_tool(ctx, "check_availability", {"service": "Haircut", "date_from": "next friday"})
    assert res.status == "ok"
    assert res.data["resolved_date"]["ambiguous"] is True
    assert "ambiguous" in res.message


def test_take_message_and_request_human(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    call = _call(db)
    ctx = _ctx(db, settings, calendar, call)
    msg = run_tool(
        ctx,
        "take_message",
        {
            "name": "Hamza",
            "callback_number": "+923001234567",
            "message": "Please call about a bridal package",
        },
    )
    assert msg.status == "ok"
    # Same message retried -> still one row.
    run_tool(
        ctx,
        "take_message",
        {
            "name": "Hamza",
            "callback_number": "+923001234567",
            "message": "Please call about a bridal package",
        },
    )
    human = run_tool(ctx, "request_human", {"name": "Hamza"})
    assert human.status == "ok"  # demo: urgent message, caller id used as callback
    rows = list(db.scalars(select(Message).order_by(Message.id)))
    assert len(rows) == 2 and rows[1].urgent and not rows[0].urgent
    jobs = db.scalar(select(func.count(Job.id)).where(Job.kind == "send_staff_message"))
    assert jobs == 2


def test_request_human_transfers_when_enabled(db, settings, calendar, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "transfer_enabled", True)
    monkeypatch.setattr(settings, "handoff_number", "+15550100199")
    ctx = _ctx(db, settings, calendar, _call(db, channel="phone"))
    res = run_tool(ctx, "request_human", {"name": "Hamza"})
    assert res.status == "transferred"
    assert res.data["transfer_to"] == "+15550100199"
    # Web callers can't be SIP-transferred: they get the urgent-message path.
    web = _ctx(db, settings, calendar, _call(db, channel="web", number=""))
    assert (
        run_tool(web, "request_human", {"name": "Sana", "callback_number": "+923004445566"}).status
        == "ok"
    )


# ---------------------------------------------------------------- review fixes


def test_rebooking_a_moved_slot_creates_a_new_booking(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    """Book 2:30, move it, then book 2:30 again in the same call: a second booking, not a
    replay of the first (which now sits at another time)."""
    call = _call(db)
    ctx = _ctx(db, settings, calendar, call)
    first_slot = _offer(ctx, staff="Sara")[0]
    assert _book(ctx, first_slot).status == "ok"
    new_slot = _offer(ctx, when="wednesday", staff="Sara")[0]
    moved = run_tool(
        ctx,
        "reschedule_appointment",
        {
            "contact": "ayesha.k@example.com",
            "date": "tomorrow",
            "new_slot_id": new_slot["slot_id"],
            "caller_confirmed": True,
        },
    )
    assert moved.status == "ok", moved.message
    _offer(ctx, staff="Sara")
    again = _book(ctx, first_slot, customer_name="Sana Khan", email="sana@example.com")
    assert again.status == "ok", again.message
    assert again.data["already_existed"] is False
    assert again.data["start_utc"] == first_slot["start_utc"]
    assert db.scalar(select(func.count(Appointment.id))) == 2


def test_slot_offered_for_one_service_cannot_be_booked_for_another(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    trim_slot = _offer(ctx, service="Haircut", staff="Sara")[0]
    res = _book(ctx, trim_slot, service="Hair colour")
    assert res.status == "invalid"
    assert "offered for Haircut" in res.message
    assert db.scalar(select(func.count(Appointment.id))) == 0
    # A loosely named service still books the service the time was offered for.
    assert _book(ctx, trim_slot, service="haircut please").status == "ok"


def test_wrong_appointment_ref_never_falls_back_to_another_booking(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    assert _book(ctx, _offer(ctx)[0]).status == "ok"
    res = run_tool(
        ctx,
        "cancel_appointment",
        {
            "contact": "ayesha.k@example.com",
            "date": "tomorrow",
            "appointment_ref": "ffffffff",
            "caller_confirmed": True,
        },
    )
    assert res.status == "not_found"
    assert db.scalar(select(Appointment)).status == "booked"


class _FlakyCalendar(LocalCalendar):
    fail_upsert = False

    def upsert_event(self, calendar_id: str, event_id: str, **kw) -> str:  # type: ignore[no-untyped-def, override]
        if self.fail_upsert:
            raise RuntimeError("calendar down")
        return super().upsert_event(calendar_id, event_id, **kw)


def _separate_calendars(db) -> None:  # type: ignore[no-untyped-def]
    from app.models import Staff

    for s in db.scalars(select(Staff)):
        s.calendar_id = f"{s.name.lower()}@cal"
    db.commit()


def test_failed_move_to_another_calendar_keeps_the_original_event(db, settings) -> None:  # type: ignore[no-untyped-def]
    _separate_calendars(db)
    calendar = _FlakyCalendar()
    ctx = _ctx(db, settings, calendar, _call(db))
    assert _book(ctx, _offer(ctx, staff="Omar")[0]).status == "ok"
    appt = db.scalar(select(Appointment))
    event_id, original_start = appt.calendar_event_id, appt.start_utc
    assert calendar.events[event_id]["calendar_id"] == "omar@cal"

    sara_slot = _offer(ctx, when="wednesday", staff="Sara")[0]
    move = {
        "contact": "ayesha.k@example.com",
        "date": "tomorrow",
        "new_slot_id": sara_slot["slot_id"],
        "caller_confirmed": True,
    }
    calendar.fail_upsert = True
    assert run_tool(ctx, "reschedule_appointment", move).status == "error"
    db.expire_all()
    assert db.scalar(select(Appointment)).start_utc == original_start
    assert calendar.events[event_id]["calendar_id"] == "omar@cal"  # still on Omar's calendar

    calendar.fail_upsert = False
    assert run_tool(ctx, "reschedule_appointment", move).status == "ok"
    assert calendar.events[event_id]["calendar_id"] == "sara@cal"


def test_cancel_restores_event_if_commit_fails(db, settings, calendar, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(db, settings, calendar, _call(db))
    assert _book(ctx, _offer(ctx)[0]).status == "ok"
    appt = db.scalar(select(Appointment))
    event_id = appt.calendar_event_id

    def broken_commit() -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(db, "commit", broken_commit)
    with pytest.raises(RuntimeError):
        booking_svc.cancel(db, calendar, settings, appt)
    monkeypatch.undo()
    assert event_id in calendar.events
    db.expire_all()
    assert db.scalar(select(Appointment)).status == "booked"


def test_stale_copy_of_our_own_event_does_not_block_a_slot(db, settings, calendar) -> None:  # type: ignore[no-untyped-def]
    """A booking that moved can leave its old event behind (clean-up failed): the database
    is the source of truth, so that leftover must not hide the old time."""
    from app.services.calendar import BusyEvent

    ctx = _ctx(db, settings, calendar, _call(db))
    slot = _offer(ctx, staff="Sara")[0]
    assert _book(ctx, slot).status == "ok"
    appt = db.scalar(select(Appointment))
    start = datetime.fromisoformat(slot["start_utc"])
    calendar.external.append(
        ("", BusyEvent(appt.calendar_event_id, start, start + timedelta(minutes=45), appt.staff_id))
    )
    later = datetime.fromisoformat(_offer(ctx, when="wednesday", staff="Sara")[0]["start_utc"])
    booking_svc.reschedule(
        db, calendar, settings, appt, new_start_utc=later, new_staff_id=None, now_utc=NOW
    )
    offered = [s["slot_id"] for s in _offer(ctx, staff="Sara")]
    assert slot["slot_id"] in offered
