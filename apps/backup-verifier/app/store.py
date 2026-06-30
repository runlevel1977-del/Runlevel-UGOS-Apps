# -*- coding: utf-8 -*-
"""Job persistence under /data."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("BACKUP_VERIFIER_DATA", "/data"))
JOBS_FILE = DATA_DIR / "jobs.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "verifier.log"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_jobs() -> list[dict[str, Any]]:
    _ensure_data_dir()
    if not JOBS_FILE.is_file():
        return []
    with JOBS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_jobs(jobs: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    with JOBS_FILE.open("w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def get_job(job_id: str) -> dict[str, Any] | None:
    return next((j for j in load_jobs() if j.get("id") == job_id), None)


def update_job(job_id: str, **fields: Any) -> None:
    jobs = load_jobs()
    for j in jobs:
        if j.get("id") == job_id:
            j.update(fields)
            break
    save_jobs(jobs)


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def append_log(line: str) -> None:
    _ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")


def load_settings() -> dict[str, Any]:
    _ensure_data_dir()
    if not SETTINGS_FILE.is_file():
        return {}
    with SETTINGS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict[str, Any]) -> None:
    _ensure_data_dir()
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def read_log_tail(max_lines: int = 100) -> str:
    if not LOG_FILE.is_file():
        return ""
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])
