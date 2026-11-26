"""A small in-memory sliding-window rate limit for the assistant endpoint.

One process, one window: good enough for a single API instance (the demo and the course
project). Behind several workers each one counts on its own, so the real limit is a multiple.
"""

import threading
import time
from collections import defaultdict, deque

from ai_commerce_marketplace.core.exceptions import AppError


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many messages. Please wait a moment and try again."


class SlidingWindowLimiter:
    def __init__(self, window_s: float = 60.0) -> None:
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, now: float | None = None) -> None:
        """Record one hit for ``key`` or raise RateLimitedError. ``limit <= 0`` disables it."""
        if limit <= 0:
            return
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimitedError(
                    details={"retry_after_s": int(self.window_s - (now - hits[0])) + 1}
                )
            hits.append(now)
            if len(self._hits) > 10_000:  # keep memory bounded
                for k in [
                    k for k, v in self._hits.items() if not v or now - v[-1] >= self.window_s
                ]:
                    del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


assistant_limiter = SlidingWindowLimiter()
