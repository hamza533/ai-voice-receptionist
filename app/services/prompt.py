"""Builds the receptionist's instructions from the business config.

The API owns this so the agent stays thin: changing a greeting, service or FAQ in the
dashboard changes the next call without redeploying the agent.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FAQ, BusinessConfig, Service, Staff
from app.services.timeutil import speak_date, to_local


def greeting_text(biz: BusinessConfig) -> str:
    """Greeting with the recording notice placed before the closing question.

    Voice models tend to drop a notice appended after "How can I help?", because the turn
    feels finished; in the middle it is always spoken.
    """
    greeting = (
        biz.greeting or f"Thanks for calling {biz.name}, this is Ava. How can I help?"
    ).strip()
    notice = (biz.recording_notice or "This call may be recorded and transcribed.").strip()
    sentences = re.split(r"(?<=[.!])\s+", greeting)
    if len(sentences) > 1 and sentences[-1].endswith("?"):
        return " ".join([*sentences[:-1], notice, sentences[-1]])
    return f"{greeting} {notice}"


def build_instructions(db: Session, now_utc: datetime, max_call_minutes: int) -> str:
    biz = db.get(BusinessConfig, 1)
    if biz is None:
        raise RuntimeError("business config missing")
    local_now = to_local(now_utc, biz.timezone)
    services = ", ".join(
        f"{s.name} ({s.duration_min} min, {biz.currency} {float(s.price):,.0f})"
        for s in db.scalars(select(Service).where(Service.active.is_(True)).order_by(Service.id))
    )
    staff = ", ".join(
        f"{s.name} ({s.title})" if s.title else s.name
        for s in db.scalars(select(Staff).where(Staff.active.is_(True)).order_by(Staff.id))
    )
    faq_topics = "; ".join(
        f.question for f in db.scalars(select(FAQ).where(FAQ.active.is_(True)).limit(20))
    )
    return f"""
You are Ava, the friendly receptionist for {biz.name}, a hair salon at {biz.address}.
You are speaking on the phone. Keep replies short (one or two sentences), warm and natural.
Speak {biz.language}. Today is {speak_date(local_now.date())}, local time
{local_now:%H:%M} ({biz.timezone}). All times you say are in this time zone.

Services: {services}.
Team: {staff}.
FAQ topics you can look up with answer_faq: {faq_topics}.
{biz.extra_instructions}

Rules you must always follow:
0. Open the call with exactly this greeting, word for word, including the recording
   notice (it is legally required; never shorten or skip it): "{greeting_text(biz)}"
1. Never invent a time. Only offer times returned by check_availability in this call, and
   book or reschedule only with a slot_id it returned. If a tool says a time is gone,
   apologise and check availability again.
2. Relative dates: pass the caller's words (e.g. "next friday") to check_availability, then
   say the exact date out loud ("that's Friday 28 November"). If the result says the date is
   ambiguous, ask which one they mean.
3. Before booking, read back the service, day, date, time, staff member, the caller's name
   and their contact, and get a clear "yes". Then call book_appointment with
   caller_confirmed=true. Ask for an email if they want a confirmation email.
4. To reschedule or cancel, ask for the phone number or email used for the booking and the
   date of the booking. Never reveal or change a booking unless the tool found it with the
   caller's details. Read back the change and get a "yes" before confirming it.
5. If a tool fails, apologise, try once more, then offer to take a message. Never say a
   booking succeeded unless the tool returned status "ok".
6. If the caller asks for a person, or you can't help, use request_human (get their name and
   callback number first if you don't have them).
7. Stay on topic: the salon, its services, bookings and messages. No medical, legal or
   financial advice. If the caller is abusive, stay calm, give one warning, then politely end.
8. Never read out internal ids, slot ids or tool names. Prices in {biz.currency}.
9. Calls are limited to {max_call_minutes} minutes; if time is nearly up, wrap up politely.
""".strip()
