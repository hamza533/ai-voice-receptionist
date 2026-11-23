"""Postgres-backed job queue (no Redis, no broker).

Workers claim jobs with SELECT ... FOR UPDATE SKIP LOCKED, so any number of workers can
run safely. Failed jobs are retried with exponential backoff + jitter; after
`max_attempts` they become `dead` (dead-letter) and stay visible in the database.
Every job may carry an idempotency key: enqueueing the same key twice is a no-op.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Job
from app.services.retry import backoff_delay
from app.services.timeutil import utcnow

log = logging.getLogger(__name__)

STALE_LOCK = timedelta(minutes=10)


def enqueue(
    db: Session,
    kind: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int = 5,
) -> None:
    """Add a job inside the caller's transaction (transactional outbox)."""
    values: dict[str, Any] = {
        "kind": kind,
        "payload": payload,
        "status": "queued",
        "attempts": 0,
        "max_attempts": max_attempts,
        "run_at": run_at or utcnow(),
        "idempotency_key": idempotency_key,
    }
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = pg_insert(Job).values(**values)
        if idempotency_key:
            stmt = stmt.on_conflict_do_nothing(index_elements=["idempotency_key"])
        db.execute(stmt)
    else:  # pragma: no cover - non-Postgres fallback
        if idempotency_key and db.scalar(select(Job).where(Job.idempotency_key == idempotency_key)):
            return
        db.add(Job(**values))
        db.flush()


def claim(db: Session, worker_id: str) -> Job | None:
    """Claim one due job. Also reclaims jobs whose worker died mid-run."""
    now = utcnow()
    job = db.scalars(
        select(Job)
        .where(
            or_(
                (Job.status == "queued") & (Job.run_at <= now),
                (Job.status == "running") & (Job.locked_at < now - STALE_LOCK),
            )
        )
        .order_by(Job.run_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is None:
        db.rollback()
        return None
    job.status = "running"
    job.locked_at = now
    job.locked_by = worker_id
    job.attempts += 1
    db.commit()
    return job


def complete(db: Session, job_id: int) -> None:
    db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="done", finished_at=utcnow(), locked_at=None, last_error=None)
    )
    db.commit()


def fail(db: Session, job_id: int, error: str) -> str:
    job = db.get(Job, job_id)
    if job is None:
        return "missing"
    job.last_error = error[:2000]
    job.locked_at = None
    job.locked_by = None
    if job.attempts >= job.max_attempts:
        job.status = "dead"
        job.finished_at = utcnow()
    else:
        job.status = "queued"
        job.run_at = utcnow() + timedelta(seconds=max(1.0, backoff_delay(job.attempts, 2, 300)))
    db.commit()
    return job.status


def release(db: Session, job_id: int) -> None:
    """Give a job back to the queue untouched (graceful shutdown)."""
    db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "running")
        .values(status="queued", locked_at=None, locked_by=None, attempts=Job.attempts - 1)
    )
    db.commit()
