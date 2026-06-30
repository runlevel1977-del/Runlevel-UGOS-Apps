# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("STATS_HUB_DATA", "/data"))
LOG_FILE = DATA_DIR / "stats-hub.log"
_log_lock = threading.Lock()


def append_log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg}\n"
    with _log_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)


def read_log_tail(lines: int = 120) -> str:
    if not LOG_FILE.is_file():
        return ""
    try:
        with LOG_FILE.open(encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""
