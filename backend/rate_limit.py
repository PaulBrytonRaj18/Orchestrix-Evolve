"""In-process sliding-window rate limiter for auth endpoints.

Fine for a single instance. With several replicas use a shared store (e.g. Redis)
or the edge proxy's rate limiting instead, since each process counts separately.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, max_keys: int = 50_000) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def check(self, key: str, max_requests: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= max_requests:
                retry_after = max(int(window_seconds - (now - hits[0])), 1)
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            hits.append(now)
            if len(self._hits) > self._max_keys:
                self._evict(now, window_seconds)

    def _evict(self, now: float, window_seconds: int) -> None:
        stale = [k for k, v in self._hits.items() if not v or now - v[-1] >= window_seconds]
        for k in stale:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Behind a proxy, uvicorn's --proxy-headers sets request.client from X-Forwarded-For.
    return request.client.host if request.client else "unknown"


def rate_limited(scope: str, max_requests: int, window_seconds: int):
    """FastAPI dependency factory: ``Depends(rate_limited("login", 10, 300))``."""

    def dependency(request: Request) -> None:
        limiter.check(f"{scope}:{client_ip(request)}", max_requests, window_seconds)

    return dependency
