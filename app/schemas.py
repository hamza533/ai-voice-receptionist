"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class MeOut(ORM):
    id: int
    email: str
    name: str
    role: str


class LoginOut(BaseModel):
    user: MeOut
    csrf_token: str


# ---------------------------------------------------------------- agent


class CallStartIn(BaseModel):
    channel: Literal["web", "phone"]
    room_name: str = Field(max_length=128)
    caller_number: str = Field(default="", max_length=40)


class CallStartOut(BaseModel):
    allowed: bool
    reason: str = ""
    call_id: uuid.UUID | None = None
    max_call_seconds: int = 600
    greeting: str = ""
    instructions: str = ""
    voice: str = ""
    language: str = "en-US"
    transfer_enabled: bool = False


class TurnIn(BaseModel):
    speaker: Literal["caller", "agent", "system"]
    text: str = Field(max_length=10_000)
    ts: datetime


class CallEndIn(BaseModel):
    ended_at: datetime
    end_reason: str = Field(default="hangup", max_length=64)
    turns: list[TurnIn] = Field(default_factory=list, max_length=2000)
    latency_ms: list[int] = Field(default_factory=list, max_length=2000)
    interruptions: int = 0
    audio_input_tokens: int = 0
    audio_output_tokens: int = 0
    text_tokens: int = 0


class ToolCallIn(BaseModel):
    call_id: uuid.UUID | None = None
    args: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- dashboard


class ToolCallOut(ORM):
    id: int
    tool: str
    args: dict[str, Any]
    result_status: str
    result_summary: str
    latency_ms: int
    created_at: datetime


class TurnOut(ORM):
    speaker: str
    text: str
    ts: datetime


class CallListItem(BaseModel):
    id: uuid.UUID
    channel: str
    caller: str
    started_at: datetime
    duration_s: int | None
    outcome: str | None
    summary: str | None
    status: str


class CallList(BaseModel):
    items: list[CallListItem]
    total: int
    counts: dict[str, int]


class AppointmentOut(BaseModel):
    id: uuid.UUID
    ref: str
    service: str
    service_id: int
    staff: str
    staff_id: int
    staff_color: str
    start_utc: datetime
    end_utc: datetime
    customer_name: str
    phone: str
    email: str
    status: str
    source: Literal["ai", "manual"]
    call_id: uuid.UUID | None
    calendar_synced: bool


class CallDetail(BaseModel):
    id: uuid.UUID
    channel: str
    caller: str
    started_at: datetime
    ended_at: datetime | None
    duration_s: int | None
    outcome: str | None
    summary: str | None
    status: str
    end_reason: str | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    interruptions: int
    est_cost_usd: float
    turns: list[TurnOut]
    tool_calls: list[ToolCallOut]
    appointments: list[AppointmentOut]


class MessageOut(ORM):
    id: int
    call_id: uuid.UUID | None
    name: str
    callback_number: str
    text: str
    urgent: bool
    handled: bool
    created_at: datetime


class MessagePatch(BaseModel):
    handled: bool


class BusinessIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(max_length=64)
    address: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=40)
    website: str = Field(default="", max_length=255)
    currency: str = Field(default="USD", max_length=8)
    greeting: str = Field(default="", max_length=500)
    recording_notice: str = Field(default="", max_length=300)
    voice: str = Field(default="Aoede", max_length=64)
    language: str = Field(default="en-US", max_length=16)
    handoff_number: str = Field(default="", max_length=40)
    staff_notify_email: str = Field(default="", max_length=255)
    email_signature: str = Field(default="", max_length=1000)
    extra_instructions: str = Field(default="", max_length=2000)
    sms_confirmations: bool = True
    sms_reminders: bool = True
    reminder_hours: int = Field(default=24, ge=1, le=72)
    waitlist_enabled: bool = True
    waitlist_hold_minutes: int = Field(default=30, ge=5, le=240)


class BusinessOut(BusinessIn, ORM):
    setup_completed: bool = False


class ServiceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    duration_min: int = Field(ge=5, le=600)
    price: Decimal = Field(ge=0, le=10_000_000)
    buffer_min: int = Field(default=0, ge=0, le=240)
    active: bool = True
    staff_ids: list[int] = Field(default_factory=list)


class ServiceOut(ORM):
    id: int
    name: str
    description: str
    duration_min: int
    price: Decimal
    buffer_min: int
    active: bool
    staff_ids: list[int] = Field(default_factory=list)


class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=120)
    calendar_id: str = Field(default="", max_length=255)
    color: str = Field(default="#0f766e", pattern=r"^#[0-9a-fA-F]{6}$")
    active: bool = True


class ShiftIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _order(self) -> ShiftIn:
        if self.end_time <= self.start_time:
            raise ValueError("A shift must end after it starts")
        return self


class ShiftOut(ShiftIn, ORM):
    pass


class StaffOut(StaffIn, ORM):
    id: int
    shifts: list[ShiftOut] = Field(default_factory=list)


class TimeOffIn(BaseModel):
    """`once`: a period in business-local time (all day = 00:00 to 00:00 the next day).
    `weekly`: a recurring break on one weekday."""

    staff_id: int
    kind: Literal["once", "weekly"]
    start_local: datetime | None = None
    end_local: datetime | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    label: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def _complete(self) -> TimeOffIn:
        if self.kind == "once":
            if not self.start_local or not self.end_local or self.end_local <= self.start_local:
                raise ValueError("Time off needs a start and an end after it")
        elif self.weekday is None or not self.start_time or not self.end_time:
            raise ValueError("A weekly break needs a weekday, start and end time")
        elif self.end_time <= self.start_time:
            raise ValueError("A break must end after it starts")
        return self


class TimeOffOut(ORM):
    id: int
    staff_id: int
    kind: str
    start_utc: datetime | None
    end_utc: datetime | None
    weekday: int | None
    start_time: time | None
    end_time: time | None
    label: str


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    open_time: time
    close_time: time


class HoursOut(HoursIn, ORM):
    id: int


class HolidayIn(BaseModel):
    date: date
    label: str = Field(default="", max_length=120)


class HolidayOut(HolidayIn, ORM):
    id: int


class FaqIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)
    tags: str = Field(default="", max_length=255)
    active: bool = True


class FaqOut(FaqIn, ORM):
    id: int


class WebCallTokenOut(BaseModel):
    token: str
    url: str
    room: str
    identity: str
    expires_in: int


# ---------------------------------------------------------------- waitlist


class WaitlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=40)
    service_id: int
    staff_id: int | None = None
    day: date
    time_of_day: Literal["any", "morning", "afternoon", "evening"] = "any"
    notes: str = Field(default="", max_length=500)


class WaitlistOut(BaseModel):
    id: int
    name: str
    phone: str
    service: str
    service_id: int
    staff: str | None
    day: date
    time_of_day: str
    notes: str
    status: str
    offer_start_utc: datetime | None
    offer_staff: str | None
    offer_expires_at: datetime | None
    created_at: datetime
    source: Literal["ai", "manual"]
