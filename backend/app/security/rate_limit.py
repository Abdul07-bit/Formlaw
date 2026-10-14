"""
Sliding-window rate limiter. In-process: correct for a single API instance.
Multi-instance deployments must swap this for a shared store (e.g. Redis) behind the same interface.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from ..core.errors import RateLimited

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

# bucket -> (max requests, window seconds)
LIMITS = {
    # login / register / refresh per IP. Behind a proxy or NAT many users can share an IP: tune with AUTH_RATE_LIMIT_PER_MINUTE.
    "auth": (int(os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE") or 10), 60),
    "login_email": (5, 900),   # failed logins per account before lockout kicks in
    "upload": (30, 60),
    "agent": (20, 60),         # pipeline / chat / research runs per user
    "public": (8, 60),         # anonymous legal assistant per IP
    "public_all": (120, 60),   # anonymous legal assistant, all visitors together
    "write": (120, 60),
    "default": (300, 60),
}


def hit(bucket: str, key: str, *, cost: int = 1) -> None:
    limit, window = LIMITS.get(bucket, LIMITS["default"])
    now = time.monotonic()
    with _lock:
        q = _hits[(bucket, key)]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) + cost > limit:
            retry = int(window - (now - q[0])) + 1 if q else window
            raise RateLimited(f"Too many requests. Try again in {retry}s.", details={"retry_after": retry})
        q.extend([now] * cost)


def reset() -> None:
    with _lock:
        _hits.clear()
