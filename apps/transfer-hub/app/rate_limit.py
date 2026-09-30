# -*- coding: utf-8 -*-
"""Simple per-IP sliding window (no extra deps)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def allow(bucket: str, ip: str, *, max_n: int = 10, window_sec: int = 300) -> bool:
    key = f"{bucket}:{ip or 'unknown'}"
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_sec:
            q.popleft()
        if len(q) >= max_n:
            return False
        q.append(now)
        return True
