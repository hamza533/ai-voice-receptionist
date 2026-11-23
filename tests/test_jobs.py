"""Integration tests for the Postgres job queue, emails and retention purge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.jobs import queue
from app.jobs.worker import Worker
from app.models import Call, EmailOutbox, Job, Message, TranscriptTurn
from app.services.email import send_email

pytestmark = pytest.mark.integration


def test_enqueue_is_idempotent(db) -> None:  # type: ignore[no-untyped-def]
    for _ in range(3):
        queue.enqueue(db, "purge", {}, idempotency_key="purge:2025-11-24")
    db.commit()
    assert db.scalar(select(func.count(Job.id))) == 1


def test_skip_locked_claims_each_job_once(db) -> None:  # type: ignore[no-untyped-def]
    for i in range(4):
        queue.enqueue(db, "purge", {}, idempotency_key=f"k{i}")
    db.commit()
    claimed = set()
    sessions = [SessionLocal() for _ in range(4)]
    for s in sessions:
        job = queue.claim(s, "w")
        assert job is not None
        claimed.add(job.id)
    assert len(claimed) == 4
    assert queue.claim(SessionLocal(), "w") is None
    for s in sessions:
        s.close()


def test_failing_job_retries_then_dead_letters(db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.jobs import handlers

    def boom(*_a, **_k) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("smtp down")

    monkeypatch.setitem(handlers.HANDLERS, "send_staff_message", boom)
    monkeypatch.setattr("app.jobs.worker.HANDLERS", handlers.HANDLERS)
    queue.enqueue(db, "send_staff_message", {"message_id": 1}, max_attempts=2)
    db.commit()
    w = Worker()
    assert w.run_once()
    job = db.scalar(select(Job))
    db.refresh(job)
    assert job.status == "queued" and job.attempts == 1 and "smtp down" in job.last_error
    assert job.run_at > datetime.now(UTC)  # backoff
    job.run_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert w.run_once()
    db.refresh(job)
    assert job.status == "dead"


def test_release_returns_job_to_queue(db) -> None:  # type: ignore[no-untyped-def]
    queue.enqueue(db, "purge", {})
    db.commit()
    job = queue.claim(db, "w")
    queue.release(db, job.id)
    db.refresh(job)
    assert job.status == "queued" and job.attempts == 0


def test_email_outbox_sends_once(db, settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sent: list[str] = []

    class FakeSMTP:
        def __init__(self, *a, **k) -> None:  # type: ignore[no-untyped-def]
            pass

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *a) -> None:  # type: ignore[no-untyped-def]
            pass

        def ehlo(self) -> None:
            pass

        def has_extn(self, _: str) -> bool:
            return False

        def login(self, *a) -> None:  # type: ignore[no-untyped-def]
            pass

        def send_message(self, msg) -> None:  # type: ignore[no-untyped-def]
            sent.append(msg["To"])

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    for _ in range(3):
        status = send_email(
            db,
            settings,
            key="email:x:booked",
            to="a@example.com",
            subject="Hi",
            body="Body",
            kind="customer_booked",
        )
    assert status == "sent" and sent == ["a@example.com"]
    assert db.scalar(select(func.count(EmailOutbox.id))) == 1


def test_email_skipped_without_smtp(db, settings) -> None:  # type: ignore[no-untyped-def]
    assert (
        send_email(db, settings, key="k", to="a@example.com", subject="s", body="b", kind="t")
        == "skipped"
    )


def test_retention_purge(db, settings) -> None:  # type: ignore[no-untyped-def]
    old = datetime.now(UTC) - timedelta(days=settings.transcript_retention_days + 1)
    new = datetime.now(UTC) - timedelta(days=1)
    calls = []
    for started in (old, new):
        c = Call(
            channel="phone",
            room_name="r",
            caller_number="+923001234567",
            started_at=started,
            status="processed",
            summary="Ayesha booked a haircut",
        )
        db.add(c)
        db.flush()
        db.add(TranscriptTurn(call_id=c.id, speaker="caller", text="hi", ts=started))
        calls.append(c)
    db.add(
        Message(
            name="Ayesha",
            callback_number="+923001234567",
            text="call me",
            handled=True,
            created_at=old,
        )
    )
    db.commit()
    from app.jobs.handlers import handle_purge

    handle_purge(db, settings, {})
    db.expire_all()
    remaining = {t.call_id for t in db.scalars(select(TranscriptTurn))}
    assert remaining == {calls[1].id}
    db.refresh(calls[0])
    assert calls[0].caller_number == "" and "purged" in calls[0].summary
    assert db.scalar(select(Message)).name == "[purged]"


def test_periodic_jobs_scheduled_once_per_day(db, settings) -> None:  # type: ignore[no-untyped-def]
    w = Worker(settings)
    w.schedule_periodic()
    w._last_schedule = None  # force a second scheduling pass on the same day
    w.schedule_periodic()
    assert db.scalar(select(func.count(Job.id)).where(Job.kind == "purge")) == 1
