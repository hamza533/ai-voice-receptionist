"""Load the demo business (sample_data/luma_hair_studio.yaml) and synthetic activity.

`python -m app.seed`            -> business config only (idempotent upsert)
`python -m app.seed --demo`     -> plus synthetic calls, bookings and messages
All people and numbers are synthetic.
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.logging_setup import configure_logging
from app.models import (
    FAQ,
    Appointment,
    BusinessConfig,
    Call,
    Holiday,
    Message,
    OpeningHours,
    Service,
    Staff,
    ToolCall,
    TranscriptTurn,
)
from app.services.calendar import calendar_for_staff, event_id_for, get_calendar
from app.services.timeutil import speak_time, utcnow

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "luma_hair_studio.yaml"


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def seed_business(db: Session, path: Path = SAMPLE) -> None:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    biz = db.get(BusinessConfig, 1) or BusinessConfig(id=1)
    for k, v in data["business"].items():
        setattr(biz, k, v)
    db.add(biz)

    staff_by_name: dict[str, Staff] = {}
    for s in data["staff"]:
        row = db.scalar(select(Staff).where(Staff.name == s["name"])) or Staff(name=s["name"])
        row.title = s.get("title", "")
        row.color = s.get("color", "#0f766e")
        row.calendar_id = s.get("calendar_id", "")
        row.active = True
        db.add(row)
        staff_by_name[row.name] = row
    db.flush()

    for s in data["services"]:
        svc = db.scalar(select(Service).where(Service.name == s["name"])) or Service(name=s["name"])
        svc.description = s.get("description", "")
        svc.duration_min = s["duration_min"]
        svc.price = Decimal(str(s["price"]))
        svc.buffer_min = s.get("buffer_min", 0)
        svc.active = True
        svc.staff = [staff_by_name[n] for n in s.get("staff", [])]
        db.add(svc)

    db.execute(delete(OpeningHours))
    for h in data["opening_hours"]:
        db.add(
            OpeningHours(weekday=h["weekday"], open_time=_t(h["open"]), close_time=_t(h["close"]))
        )
    db.execute(delete(Holiday))
    for h in data.get("holidays") or []:
        db.add(Holiday(date=h["date"], label=h.get("label", "")))

    existing = {f.question: f for f in db.scalars(select(FAQ))}
    for f in data["faqs"]:
        faq_row = existing.get(f["question"]) or FAQ(question=f["question"])
        faq_row.answer = f["answer"]
        faq_row.tags = f.get("tags", "")
        faq_row.active = True
        db.add(faq_row)
    db.commit()


# ---------------------------------------------------------------- synthetic activity

FIRST = [
    "Ayesha",
    "Hamza",
    "Sana",
    "Bilal",
    "Maria",
    "Usman",
    "Zara",
    "Ali",
    "Hina",
    "Daniyal",
    "Fatima",
    "Imran",
    "Noor",
    "Kamran",
    "Mehwish",
    "Saad",
]
LAST = ["Khan", "Ahmed", "Siddiqui", "Malik", "Raza", "Qureshi", "Hussain", "Shah", "Iqbal"]

OUTCOME_WEIGHTS = [
    ("booked", 46),
    ("faq_answered", 26),
    ("rescheduled", 8),
    ("cancelled", 5),
    ("message_taken", 7),
    ("handed_to_human", 4),
    ("abandoned", 4),
]


def _fake_phone(rng: random.Random) -> str:
    return f"+92300{rng.randint(1000000, 9999999)}"


def _conversation(
    outcome: str, name: str, service: str, staff: str, when: str, faq: FAQ | None
) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
    """Returns (turns, tool_calls) for a synthetic call."""
    greet = (
        "agent",
        "Thank you for calling Luma Hair Studio, this is Ava. This call may be "
        "recorded and transcribed. How can I help you today?",
    )
    turns: list[tuple[str, str]] = [greet]
    tools: list[tuple[str, str, str]] = []
    if outcome in {"booked", "rescheduled"}:
        verb = "book" if outcome == "booked" else "move my appointment to"
        turns += [
            ("caller", f"Hi, I'd like to {verb} a {service.lower()} with {staff}, if possible."),
            ("agent", f"Of course. {staff} has {when} free. Would that work?"),
            ("caller", "Yes, that works."),
            (
                "agent",
                f"Great. Just to confirm: {service} with {staff} on {when}, for {name}. "
                "Shall I go ahead?",
            ),
            ("caller", "Yes please."),
            ("agent", f"Done, you're all set for {when}. A confirmation email is on its way."),
        ]
        tools.append(("check_availability", "ok", f"3 slots for {service}"))
        if outcome == "rescheduled":
            tools.append(("reschedule_appointment", "ok", f"Moved to {when}"))
        else:
            tools.append(("book_appointment", "ok", f"{service} with {staff}, {when}"))
    elif outcome == "cancelled":
        turns += [
            ("caller", "Hi, I need to cancel my appointment, something came up."),
            (
                "agent",
                "No problem. What's the phone number or email you booked with, and which "
                "day is it?",
            ),
            ("caller", "It's this number, the booking is tomorrow."),
            ("agent", f"I found your {service} on {when}. Shall I cancel it?"),
            ("caller", "Yes, thanks."),
            ("agent", "That's cancelled. Would you like to book another time?"),
            ("caller", "Not right now, thank you."),
        ]
        tools.append(("cancel_appointment", "ok", f"Cancelled {service} on {when}"))
    elif outcome == "faq_answered" and faq is not None:
        turns += [
            ("caller", faq.question),
            ("agent", faq.answer),
            ("caller", "Perfect, thanks."),
            ("agent", "You're welcome. Anything else I can help with?"),
        ]
        tools.append(("answer_faq", "ok", faq.question))
    elif outcome == "message_taken":
        turns += [
            ("caller", "Can Sara call me back about a bridal package?"),
            ("agent", "I'll pass that on. Can I take your name and the best number to call?"),
            ("caller", f"It's {name}, on this number."),
            ("agent", "Thanks, I've passed your message to the team and they'll call you back."),
        ]
        tools.append(("take_message", "ok", "Message saved for staff"))
    elif outcome == "handed_to_human":
        turns += [
            ("caller", "Can I speak to a real person please?"),
            (
                "agent",
                "Of course. Can I take your name and number so the team can call you "
                "straight back?",
            ),
            ("caller", f"{name}, this number is fine."),
            ("agent", "Thank you. I've alerted the team and someone will call you back shortly."),
        ]
        tools.append(("request_human", "ok", "Staff alerted (urgent)"))
    else:
        turns += [("caller", "Hello? ...")]
    return turns, tools


def seed_demo_activity(
    db: Session, settings: Settings, *, reset: bool = False, seed: int = 7
) -> None:
    rng = random.Random(seed)
    biz = db.get(BusinessConfig, 1)
    if biz is None:
        raise RuntimeError("seed the business first")
    zone = ZoneInfo(biz.timezone)
    if reset:
        db.execute(delete(Appointment))
        db.execute(delete(Message))
        db.execute(delete(Call))
        db.commit()
    elif db.scalar(select(Call.id).limit(1)) is not None:
        return  # already has activity

    services = list(db.scalars(select(Service).where(Service.active.is_(True))))
    faqs = list(db.scalars(select(FAQ).where(FAQ.active.is_(True))))
    now = utcnow()
    calendar = get_calendar(settings)
    outcomes = [o for o, _ in OUTCOME_WEIGHTS]
    weights = [w for _, w in OUTCOME_WEIGHTS]
    taken: set[tuple[int, datetime]] = set()

    def free_slot(service: Service, day_offset: int) -> tuple[Staff, datetime] | None:
        staff = sorted(service.staff, key=lambda s: s.id)
        for _ in range(30):
            member = rng.choice(staff)
            local_day = (now.astimezone(zone) + timedelta(days=day_offset)).date()
            if local_day.weekday() == 6:
                local_day += timedelta(days=1)
            hour = rng.randint(10, 19 - (service.duration_min // 60))
            minute = rng.choice([0, 30])
            start = datetime.combine(local_day, time(hour, minute), tzinfo=zone).astimezone(UTC)
            end_local = start.astimezone(zone) + timedelta(minutes=service.duration_min)
            if end_local.time() > time(20, 0) or start < now + timedelta(hours=1):
                continue
            clash = any(
                sid == member.id and abs((t - start).total_seconds()) < 2.5 * 3600
                for sid, t in taken
            )
            if not clash:
                taken.add((member.id, start))
                return member, start
        return None

    # Calls over the last 7 days, busiest on Friday/Saturday.
    for day_back in range(6, -1, -1):
        day = now - timedelta(days=day_back)
        n = rng.randint(4, 7) + (3 if day.astimezone(zone).weekday() in (4, 5) else 0)
        for _ in range(n):
            local_start = datetime.combine(
                day.astimezone(zone).date(),
                time(rng.randint(9, 20), rng.randint(0, 59)),
                tzinfo=zone,
            )
            started = local_start.astimezone(UTC)
            if started > now - timedelta(minutes=10):
                continue
            outcome = rng.choices(outcomes, weights)[0]
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            service = rng.choice(services)
            slot = (
                free_slot(service, rng.randint(1, 6))
                if outcome in {"booked", "rescheduled", "cancelled"}
                else None
            )
            staff_name = slot[0].name if slot else rng.choice(service.staff).name
            when = speak_time(slot[1], biz.timezone) if slot else "Saturday at 4 PM"
            turns, tools = _conversation(
                outcome, name, service.name, staff_name, when, rng.choice(faqs) if faqs else None
            )
            duration = 35 + 14 * len(turns) + rng.randint(0, 40)
            channel = "phone" if rng.random() < 0.6 else "web"
            call = Call(
                channel=channel,
                room_name=f"seed-{uuid.uuid4().hex[:8]}",
                caller_number=_fake_phone(rng) if channel == "phone" else "",
                started_at=started,
                ended_at=started + timedelta(seconds=duration),
                duration_s=duration,
                outcome=outcome,
                status="processed",
                end_reason="hangup",
                latency_p50_ms=rng.randint(520, 780),
                latency_p95_ms=rng.randint(900, 1400),
                interruptions=rng.randint(0, 2),
                audio_input_tokens=duration * 32,
                audio_output_tokens=duration * 20,
                est_cost_usd=round((duration * 32 * 3 + duration * 20 * 12) / 1e6, 5),
            )
            summary = {
                "booked": f"{name} booked a {service.name.lower()} with {staff_name} for {when}.",
                "rescheduled": f"{name} moved their {service.name.lower()} to {when}.",
                "cancelled": f"{name} cancelled their {service.name.lower()}.",
                "faq_answered": "Caller asked a question and was answered from the FAQ.",
                "message_taken": f"{name} asked Sara to call back about a bridal package.",
                "handed_to_human": f"{name} asked to speak to a person; staff were alerted.",
                "abandoned": "Caller hung up before saying what they needed.",
            }[outcome]
            call.summary = summary
            db.add(call)
            db.flush()
            for i, (speaker, text) in enumerate(turns):
                db.add(
                    TranscriptTurn(
                        call_id=call.id,
                        speaker=speaker,
                        text=text,
                        ts=started + timedelta(seconds=4 + i * 12),
                    )
                )
            for tool, status, s in tools:
                db.add(
                    ToolCall(
                        call_id=call.id,
                        tool=tool,
                        args={},
                        result_status=status,
                        result_summary=s,
                        latency_ms=rng.randint(90, 420),
                    )
                )
            if slot and outcome in {"booked", "rescheduled"}:
                member, start = slot
                key = f"seed:{call.id}"
                appt = Appointment(
                    service_id=service.id,
                    staff_id=member.id,
                    start_utc=start,
                    end_utc=start + timedelta(minutes=service.duration_min),
                    customer_name=name,
                    phone=_fake_phone(rng),
                    email=f"{name.split()[0].lower()}@example.com",
                    status="booked" if outcome == "booked" else "rescheduled",
                    idempotency_key=key,
                    call_id=call.id,
                )
                appt.service, appt.staff = service, member
                try:
                    appt.calendar_event_id = calendar.upsert_event(
                        calendar_for_staff(member, settings.google_calendar_id),
                        event_id_for(key),
                        summary=f"{service.name} – {name}",
                        description="Synthetic demo booking",
                        start=appt.start_utc,
                        end=appt.end_utc,
                        staff_id=member.id,
                        timezone=biz.timezone,
                    )
                except Exception:
                    appt.calendar_event_id = None
                db.add(appt)
            if outcome in {"message_taken", "handed_to_human"}:
                db.add(
                    Message(
                        call_id=call.id,
                        name=name,
                        callback_number=_fake_phone(rng),
                        text=summary,
                        urgent=outcome == "handed_to_human",
                        handled=day_back > 1,
                    )
                )
    db.commit()

    # A few bookings for today so the schedule is never empty in the demo.
    for service in services[:3]:
        slot = free_slot(service, 0)
        if slot is None:
            continue
        member, start = slot
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        key = f"seed:today:{service.id}:{start.isoformat()}"
        appt = Appointment(
            service_id=service.id,
            staff_id=member.id,
            start_utc=start,
            end_utc=start + timedelta(minutes=service.duration_min),
            customer_name=name,
            phone=_fake_phone(rng),
            email="",
            status="booked",
            idempotency_key=key,
        )
        db.add(appt)
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the demo business")
    parser.add_argument("--demo", action="store_true", help="also add synthetic activity")
    parser.add_argument("--reset", action="store_true", help="replace existing activity")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    with SessionLocal() as db:
        seed_business(db)
        if args.demo or settings.demo_mode:
            seed_demo_activity(db, settings, reset=args.reset)
    print("seed complete")


if __name__ == "__main__":
    main()
