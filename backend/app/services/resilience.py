"""Resilience helpers — retry with exponential backoff.

Wraps external API calls (GitHub, Ollama, Gemini) so transient network / 5xx /
rate-limit failures get retried instead of failing the whole pipeline run.
Keeps Phase 5's "retries on external calls" requirement without pulling in a
heavy dependency.
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retry on these (transient). Anything else is re-raised immediately.
_RETRYABLE = (
    TimeoutError,
    ConnectionError,
    asyncio.TimeoutError,
)


def _is_retryable_http_status(exc: BaseException) -> bool:
    """Treat httpx HTTPStatusError 5xx + 429 as retryable."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status is not None and (status == 429 or status >= 500)


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _RETRYABLE):
        return True
    return _is_retryable_http_status(exc)


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    description: str = "call",
) -> T:
    """Call ``func`` up to ``attempts`` times with exponential backoff + jitter.

    Only transient errors (timeouts, connection errors, HTTP 429/5xx) are
    retried; everything else raises immediately. Raises the last error if all
    attempts fail.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not is_retryable(exc) or attempt == attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay + random.uniform(0, delay * 0.25)  # jitter
            logger.warning(
                "retry[%s]: attempt %d/%d failed (%s); sleeping %.2fs",
                description,
                attempt,
                attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    # Unreachable, but keeps the type checker happy.
    assert last_exc is not None
    raise last_exc
