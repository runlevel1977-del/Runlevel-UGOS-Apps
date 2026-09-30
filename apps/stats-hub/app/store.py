# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("STATS_HUB_DATA", "/data"))
LOG_FILE = DATA_DIR / "stats-hub.log"
_log_q: queue.Queue[str] = queue.Queue(maxsize=500)
_writer_lock = threading.Lock()
_writer_started = False


def _log_writer() -> None:
    """Background writer — never block the monitor/API on a stuck /data volume."""
    while True:
        line = _log_q.get()
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass
        finally:
            _log_q.task_done()


def _ensure_writer() -> None:
    global _writer_started
    with _writer_lock:
        if _writer_started:
            return
        threading.Thread(target=_log_writer, daemon=True, name="stats-log").start()
        _writer_started = True


def append_log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg}\n"
    _ensure_writer()
    try:
        _log_q.put_nowait(line)
    except queue.Full:
        pass


def read_log_tail(lines: int = 120) -> str:
    if not LOG_FILE.is_file():
        return ""
    try:
        with LOG_FILE.open(encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""
