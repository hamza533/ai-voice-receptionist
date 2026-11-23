"""Application settings, read from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://receptionist:receptionist@localhost:5432/receptionist"
    session_secret: str = "change-me-in-env"  # noqa: S105 - placeholder, real value from env
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    cookie_secure: bool = False  # true behind HTTPS in production
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # LiveKit
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_agent_name: str = "luma-receptionist"
    web_call_token_ttl_s: int = 600

    # Gemini
    gemini_api_key: str = ""
    voice_model: str = "gemini-3.1-flash-live-preview"
    voice_name: str = "Aoede"
    llm_model: str = "gemini-3.8-flash"
    # Tried in order when the primary model is overloaded or unavailable.
    llm_fallback_models: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["gemini-3.5-flash", "gemini-3.1-flash-lite"]
    )
    llm_timeout_s: float = 30.0

    # Google Calendar
    google_service_account_json: str = ""
    google_calendar_id: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "Luma Hair Studio <no-reply@example.com>"
    staff_notify_email: str = ""

    # Agent <-> API
    agent_service_token: str = ""

    # Call handling
    transfer_enabled: bool = False
    handoff_number: str = ""
    max_call_minutes: int = 10
    booking_window_days: int = 30
    transcript_retention_days: int = 30
    slot_step_minutes: int = 15
    min_lead_minutes: int = 60

    # Demo mode
    demo_mode: bool = False
    demo_daily_calls: int = 20
    demo_max_call_minutes: int = 3
    demo_rate_limit_per_minute: int = 10
    # Proxies in front of the API that append to X-Forwarded-For (1 = the Next.js web app;
    # 2 = Vercel web app -> Render API). 0 ignores the header and uses the TCP peer.
    trusted_proxy_hops: int = 1

    # Worker
    worker_mode: Literal["embedded", "separate", "off"] = "embedded"
    worker_poll_seconds: float = 1.0

    @field_validator("allowed_origins", "llm_fallback_models", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def effective_max_call_minutes(self) -> int:
        if self.demo_mode:
            return min(self.max_call_minutes, self.demo_max_call_minutes)
        return self.max_call_minutes

    @property
    def calendar_enabled(self) -> bool:
        return bool(self.google_service_account_json and self.google_calendar_id)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def livekit_enabled(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
