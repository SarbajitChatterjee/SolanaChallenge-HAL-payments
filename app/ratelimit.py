"""Small in-memory rate limiter for public endpoints (per client IP, per route).

Good enough for one Render instance. With several instances, move this to Redis or to the edge.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: float) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_s:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


def limit(name: str, max_calls: int, window_s: float):
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        if not request.app.state.limiter.allow(f"{name}:{ip}", max_calls, window_s):
            raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    return dependency
