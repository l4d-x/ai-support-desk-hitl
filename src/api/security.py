from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import deque

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """Fail closed: if API_KEY isn't configured the protected endpoints refuse everything."""
    expected = get_settings().api_key
    if not expected:
        raise HTTPException(status_code=503, detail="Server is missing its API_KEY setting")
    if not key or not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class MinuteLimiter:
    """Global sliding-window limiter to stay under the LLM provider's requests-per-minute cap."""

    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit, self.window_s = limit, window_s
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._hits and now - self._hits[0] > self.window_s:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                return False
            self._hits.append(now)
            return True


def email_key(email: str) -> str:
    """Usage counters are keyed by a hash so raw emails are not stored in the usage table."""
    return "email:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]
