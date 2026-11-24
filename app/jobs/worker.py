"""Job worker.

WORKER_MODE=separate  -> `python -m app.jobs.worker` in its own container (production).
WORKER_MODE=embedded  -> started in a thread inside the API process (free demo host).

Graceful shutdown: on SIGTERM the worker stops claiming, lets the in-flight job finish
(up to a grace period) and releases it back to the queue if it could not finish.
"""

from __future__ import annotations

import logging
import signal
import socket
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.jobs import queue
from app.jobs.handlers import HANDLERS
from app.logging_setup import configure_logging, request_id_var

log = logging.getLogger(__name__)


def _scheduled_jobs(settings: Settings, now: datetime) -> list[tuple[str, str, datetime]]:
    """(kind, idempotency_key, run_at) for periodic jobs. Keys are per-day, so enqueueing
    them every loop is harmless: each day's job is inserted once."""
    today = now.date().isoformat()
    jobs = [("purge", f"purge:{today}", now)]
    # Every 15 minutes: offer newly free times to the waitlist.
    quarter = f"{now:%Y-%m-%dT%H}:{now.minute // 15}"
    jobs.append(("waitlist_sweep", f"waitlist_sweep:{quarter}", now))
    if settings.demo_mode:
        # 21:00 UTC is 02:00 in Karachi: quiet hours for the demo business.
        reset_at = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC) + timedelta(
            hours=21
        )
        jobs.append(("demo_reset", f"demo_reset:{today}", reset_at))
    return jobs


class Worker:
    def __init__(self, settings: Settings | None = None, worker_id: str | None = None) -> None:
        self.settings = settings or get_settings()
        self.worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4().hex[:6]}"
        self._stop = threading.Event()
        self._last_schedule: float | None = None  # None = never ran (monotonic may start near 0)

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def schedule_periodic(self) -> None:
        if self._last_schedule is not None and time.monotonic() - self._last_schedule < 300:
            return
        self._last_schedule = time.monotonic()
        now = datetime.now(UTC)
        with SessionLocal() as db:
            for kind, key, run_at in _scheduled_jobs(self.settings, now):
                queue.enqueue(db, kind, {}, idempotency_key=key, run_at=run_at, max_attempts=3)
            db.commit()

    def run_once(self) -> bool:
        """Claim and run one job. Returns True if a job was processed."""
        with SessionLocal() as db:
            job = queue.claim(db, self.worker_id)
            if job is None:
                return False
            job_id, kind, payload = job.id, job.kind, dict(job.payload or {})
        token = request_id_var.set(f"job-{job_id}")
        started = time.perf_counter()
        try:
            handler = HANDLERS.get(kind)
            if handler is None:
                raise RuntimeError(f"no handler for job kind '{kind}'")
            with SessionLocal() as db:
                handler(db, self.settings, payload)
            with SessionLocal() as db:
                queue.complete(db, job_id)
            log.info(
                "job done",
                extra={
                    "job_id": job_id,
                    "kind": kind,
                    "ms": int((time.perf_counter() - started) * 1000),
                },
            )
        except Exception as exc:
            with SessionLocal() as db:
                status = queue.fail(db, job_id, f"{type(exc).__name__}: {exc}")
            log.exception("job failed", extra={"job_id": job_id, "kind": kind, "status": status})
        finally:
            request_id_var.reset(token)
        return True

    def run_forever(self) -> None:
        log.info("worker started", extra={"worker_id": self.worker_id})
        while not self.stopping:
            try:
                self.schedule_periodic()
                if not self.run_once():
                    self._stop.wait(self.settings.worker_poll_seconds)
            except Exception:
                log.exception("worker loop error")
                self._stop.wait(5)
        log.info("worker stopped", extra={"worker_id": self.worker_id})


def start_embedded(settings: Settings) -> Worker:
    worker = Worker(settings)
    thread = threading.Thread(target=worker.run_forever, name="job-worker", daemon=True)
    thread.start()
    worker._thread = thread  # type: ignore[attr-defined]
    return worker


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    worker = Worker(settings)

    def _graceful(signum: int, _frame: object) -> None:
        log.info("shutdown signal received", extra={"signal": signum})
        worker.stop()

    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)
    worker.run_forever()


if __name__ == "__main__":
    main()
