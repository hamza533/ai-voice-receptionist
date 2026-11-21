"""Dashboard API: auth, calls, appointments, messages, stats."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Appointment, BusinessConfig, Call, Message, User
from app.schemas import (
    AppointmentOut,
    CallDetail,
    CallList,
    CallListItem,
    LoginIn,
    LoginOut,
    MeOut,
    MessageOut,
    MessagePatch,
    ToolCallOut,
    TurnOut,
)
from app.security import (
    client_ip,
    create_session,
    current_user,
    destroy_session,
    hash_password,
    hit_rate_limit,
    verify_password,
)
from app.services import booking as booking_svc
from app.services.calendar import get_calendar
from app.services.privacy import mask_phone
from app.services.timeutil import utcnow

router = APIRouter(prefix="/api", tags=["dashboard"])

DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


# ---------------------------------------------------------------- auth


@router.post("/auth/login", response_model=LoginOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginOut:
    ip = client_ip(request)
    if hit_rate_limit(db, f"login:{ip}", limit=10, window=timedelta(minutes=5)) or hit_rate_limit(
        db, f"login-user:{body.email.lower()}", limit=10, window=timedelta(minutes=15)
    ):
        raise HTTPException(429, "Too many sign-in attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    # Verify against a dummy hash when the user doesn't exist, to keep timing similar.
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not user or not ok or not user.active:
        raise HTTPException(401, "Email or password is incorrect")
    csrf = create_session(db, user, response, settings)
    return LoginOut(user=MeOut.model_validate(user), csrf_token=csrf)


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> dict[str, bool]:
    destroy_session(db, request, response)
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)) -> User:
    return user


# ---------------------------------------------------------------- helpers


def _tz(db: Session) -> ZoneInfo:
    biz = db.get(BusinessConfig, 1)
    return ZoneInfo(biz.timezone if biz else "UTC")


def _caller(call: Call) -> str:
    if call.channel == "web":
        return "Web caller"
    return mask_phone(call.caller_number) if call.caller_number else "Unknown number"


def appointment_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id,
        ref=str(a.id)[:8],
        service=a.service.name,
        service_id=a.service_id,
        staff=a.staff.name,
        staff_id=a.staff_id,
        staff_color=a.staff.color,
        start_utc=a.start_utc,
        end_utc=a.end_utc,
        customer_name=a.customer_name,
        phone=mask_phone(a.phone) if a.phone else "",
        email=a.email,
        status=a.status,
        source="ai" if a.call_id else "manual",
        call_id=a.call_id,
        calendar_synced=bool(a.calendar_event_id),
    )


def _day_bounds(d: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    lo = datetime.combine(d, time.min, tzinfo=zone)
    return lo, lo + timedelta(days=1)


# ---------------------------------------------------------------- calls


@router.get("/calls", response_model=CallList)
def list_calls(
    outcome: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> CallList:
    zone = _tz(db)
    base = select(Call)
    if date_from:
        base = base.where(Call.started_at >= _day_bounds(date_from, zone)[0])
    if date_to:
        base = base.where(Call.started_at < _day_bounds(date_to, zone)[1])
    if q:
        like = f"%{q.strip()}%"
        base = base.where(or_(Call.summary.ilike(like), Call.caller_number.ilike(like)))
    sub = base.subquery()
    counts_rows = db.execute(select(sub.c.outcome, func.count()).group_by(sub.c.outcome)).all()
    counts = {str(k or "in_progress"): int(v) for k, v in counts_rows}
    counts["all"] = sum(counts.values())
    stmt = base
    if outcome and outcome != "all":
        stmt = stmt.where(Call.outcome == outcome)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Call.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        CallListItem(
            id=c.id,
            channel=c.channel,
            caller=_caller(c),
            started_at=c.started_at,
            duration_s=c.duration_s,
            outcome=c.outcome,
            summary=c.summary,
            status=c.status,
        )
        for c in rows
    ]
    return CallList(items=items, total=total, counts=counts)


@router.get("/calls/{call_id}", response_model=CallDetail)
def get_call(
    call_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> CallDetail:
    c = db.get(Call, call_id)
    if c is None:
        raise HTTPException(404, "Call not found")
    appts = db.scalars(select(Appointment).where(Appointment.call_id == c.id))
    return CallDetail(
        id=c.id,
        channel=c.channel,
        caller=_caller(c),
        started_at=c.started_at,
        ended_at=c.ended_at,
        duration_s=c.duration_s,
        outcome=c.outcome,
        summary=c.summary,
        status=c.status,
        end_reason=c.end_reason,
        latency_p50_ms=c.latency_p50_ms,
        latency_p95_ms=c.latency_p95_ms,
        interruptions=c.interruptions,
        est_cost_usd=c.est_cost_usd or 0.0,
        turns=[TurnOut.model_validate(t) for t in c.turns],
        tool_calls=[ToolCallOut.model_validate(t) for t in c.tool_calls],
        appointments=[appointment_out(a) for a in appts],
    )


# ---------------------------------------------------------------- appointments


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    date_from: date | None = None,
    date_to: date | None = None,
    staff_id: int | None = None,
    include_cancelled: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[AppointmentOut]:
    zone = _tz(db)
    today = utcnow().astimezone(zone).date()
    start = _day_bounds(date_from or today, zone)[0]
    end = _day_bounds(date_to or (date_from or today) + timedelta(days=6), zone)[1]
    stmt = select(Appointment).where(Appointment.start_utc >= start, Appointment.start_utc < end)
    if staff_id:
        stmt = stmt.where(Appointment.staff_id == staff_id)
    if not include_cancelled:
        stmt = stmt.where(Appointment.status != "cancelled")
    return [appointment_out(a) for a in db.scalars(stmt.order_by(Appointment.start_utc))]


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(current_user),
) -> AppointmentOut:
    appt = db.get(Appointment, appointment_id)
    if appt is None:
        raise HTTPException(404, "Appointment not found")
    try:
        appt = booking_svc.cancel(db, get_calendar(settings), settings, appt)
    except booking_svc.BookingError as exc:
        raise HTTPException(502, exc.message) from exc
    return appointment_out(appt)


# ---------------------------------------------------------------- messages


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    handled: bool | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)
) -> list[Message]:
    stmt = (
        select(Message)
        .order_by(Message.handled, Message.urgent.desc(), Message.created_at.desc())
        .limit(200)
    )
    if handled is not None:
        stmt = stmt.where(Message.handled.is_(handled))
    return list(db.scalars(stmt))


@router.patch("/messages/{message_id}", response_model=MessageOut)
def update_message(
    message_id: int,
    body: MessagePatch,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> Message:
    msg = db.get(Message, message_id)
    if msg is None:
        raise HTTPException(404, "Message not found")
    msg.handled = body.handled
    db.commit()
    return msg


# ---------------------------------------------------------------- stats


@router.get("/stats/overview")
def overview(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> dict[str, object]:
    zone = _tz(db)
    now = utcnow()
    today = now.astimezone(zone).date()
    first_day = today - timedelta(days=days - 1)
    since = _day_bounds(first_day, zone)[0]
    prev_since = since - timedelta(days=days)

    calls = list(db.scalars(select(Call).where(Call.started_at >= since)))
    prev_count = (
        db.scalar(
            select(func.count(Call.id)).where(
                Call.started_at >= prev_since, Call.started_at < since
            )
        )
        or 0
    )
    outcomes = Counter(c.outcome or "in_progress" for c in calls)
    durations = [c.duration_s for c in calls if c.duration_s]
    latencies = [c.latency_p50_ms for c in calls if c.latency_p50_ms]
    booked_appts = (
        db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.created_at >= since, Appointment.call_id.is_not(None)
            )
        )
        or 0
    )

    per_day: dict[str, int] = {}
    for i in range(days if days <= 14 else 7):
        d = today - timedelta(days=(days if days <= 14 else 7) - 1 - i)
        per_day[d.isoformat()] = 0
    for c in calls:
        key = c.started_at.astimezone(zone).date().isoformat()
        if key in per_day:
            per_day[key] += 1

    lo, hi = _day_bounds(today, zone)
    upcoming = db.scalars(
        select(Appointment)
        .where(
            Appointment.start_utc >= max(lo, now),
            Appointment.start_utc < hi,
            Appointment.status != "cancelled",
        )
        .order_by(Appointment.start_utc)
        .limit(5)
    )
    recent = db.scalars(select(Call).order_by(Call.started_at.desc()).limit(5))
    unhandled = db.scalar(select(func.count(Message.id)).where(Message.handled.is_(False))) or 0
    urgent = (
        db.scalar(
            select(func.count(Message.id)).where(
                Message.handled.is_(False), Message.urgent.is_(True)
            )
        )
        or 0
    )
    total = len(calls)
    return {
        "range": {"from": first_day.isoformat(), "to": today.isoformat(), "days": days},
        "calls": total,
        "calls_change_pct": round((total - prev_count) / prev_count * 100) if prev_count else None,
        "appointments_booked": booked_appts,
        "booking_rate": round(outcomes.get("booked", 0) / total * 100) if total else 0,
        "avg_duration_s": round(sum(durations) / len(durations)) if durations else 0,
        "median_latency_ms": sorted(latencies)[len(latencies) // 2] if latencies else None,
        "handoffs": outcomes.get("handed_to_human", 0),
        "outcomes": dict(outcomes),
        "per_day": [{"date": k, "calls": v} for k, v in per_day.items()],
        "upcoming_today": [appointment_out(a).model_dump(mode="json") for a in upcoming],
        "recent_calls": [
            CallListItem(
                id=c.id,
                channel=c.channel,
                caller=_caller(c),
                started_at=c.started_at,
                duration_s=c.duration_s,
                outcome=c.outcome,
                summary=c.summary,
                status=c.status,
            ).model_dump(mode="json")
            for c in recent
        ],
        "messages_open": unhandled,
        "messages_urgent": urgent,
        "time_saved_min": round(sum(durations) / 60) if durations else 0,
    }
