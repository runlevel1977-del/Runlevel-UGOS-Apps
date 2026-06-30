# -*- coding: utf-8 -*-
"""In-memory job progress for the Web-UI (thread-safe)."""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}


def set_progress(
    job_id: str,
    *,
    phase: str,
    percent: int,
    message: str,
    indeterminate: bool = False,
) -> None:
    pct = max(0, min(100, int(percent)))
    with _lock:
        _state[job_id] = {
            "phase": phase,
            "percent": pct,
            "message": message,
            "indeterminate": bool(indeterminate),
            "updated_at": time.time(),
        }


def clear_progress(job_id: str) -> None:
    with _lock:
        _state.pop(job_id, None)


def get_progress(job_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _state.get(job_id)
        return dict(row) if row else None


def snapshot() -> dict[str, dict[str, Any]]:
    with _lock:
        return {k: dict(v) for k, v in _state.items()}
