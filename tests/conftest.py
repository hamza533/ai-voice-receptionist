"""Test setup.

Unit tests need nothing. Integration tests (marked `integration`) run against a real
Postgres from TEST_DATABASE_URL: the schema is created with Alembic (so migrations are
tested too) and tables are truncated between tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://receptionist:receptionist@localhost:55432/receptionist_test",
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["ENVIRONMENT"] = "test"
os.environ["AGENT_SERVICE_TOKEN"] = "test-agent-token"
os.environ["WORKER_MODE"] = "off"
os.environ["DEMO_MODE"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["LIVEKIT_URL"] = "wss://test.livekit.cloud"
os.environ["LIVEKIT_API_KEY"] = "APItest"
os.environ["LIVEKIT_API_SECRET"] = "secret-test-secret-test-secret-test-1234"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3010"

# A fixed "now": Monday 24 Nov 2025, 09:00 in Karachi (04:00 UTC).
NOW = datetime(2025, 11, 24, 4, 0, tzinfo=UTC)


def _db_available() -> bool:
    try:
        import psycopg

        url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(url, connect_timeout=3):
            return True
    except Exception:
        return False


DB_OK = _db_available()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if DB_OK:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL Postgres not reachable")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def migrated() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture
def db(migrated: None) -> Iterator[object]:
    from sqlalchemy import text

    from app.db import SessionLocal, get_engine
    from app.seed import seed_business

    with get_engine().begin() as conn:
        tables = (
            conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    session = SessionLocal()
    seed_business(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def settings():  # type: ignore[no-untyped-def]
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    yield s
    get_settings.cache_clear()


@pytest.fixture
def calendar():  # type: ignore[no-untyped-def]
    from app.services.calendar import LocalCalendar

    return LocalCalendar()


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def agent_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-agent-token"}


@pytest.fixture
def admin(db):  # type: ignore[no-untyped-def]
    from app.cli import create_user

    create_user("owner@luma.example.com", "correct-horse-battery", "admin", "Owner")
    create_user("staff@luma.example.com", "correct-horse-staple", "staff", "Front desk")
    return {"email": "owner@luma.example.com", "password": "correct-horse-battery"}


def login(client, email: str, password: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}
