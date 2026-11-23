"""Retry with exponential backoff and full jitter for calls to external services."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
log = logging.getLogger(__name__)


class PermanentError(Exception):
    """Raise to stop retrying (e.g. a 4xx that will never succeed)."""


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    """Full-jitter backoff: random value in [0, min(cap, base * 2**attempt)]."""
    return random.uniform(0, min(cap, base * (2**attempt)))


def retry_call[T](
    fn: Callable[[], T],
    *,
    what: str,
    attempts: int = 3,
    base: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except PermanentError:
            raise
        except Exception as exc:
            last = exc
            if attempt == attempts - 1:
                break
            delay = backoff_delay(attempt, base)
            log.warning(
                "retrying external call",
                extra={"what": what, "attempt": attempt + 1, "delay_s": round(delay, 2)},
            )
            sleep(delay)
    assert last is not None
    raise last
