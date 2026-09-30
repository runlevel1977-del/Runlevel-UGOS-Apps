# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SECRET_RES = (
    re.compile(r"(?i)(password\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(pass\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(-U\s+)([^%\s]+)%(\S+)"),
    re.compile(r"enc:v1:[A-Za-z0-9+/=._-]+"),
)


def redact_secrets(text: str) -> str:
    out = str(text or "")
    out = _SECRET_RES[0].sub(r"\1***", out)
    out = _SECRET_RES[1].sub(r"\1***", out)
    out = _SECRET_RES[2].sub(r"\1***", out)
    out = _SECRET_RES[3].sub(r"\1\2%***", out)
    out = _SECRET_RES[4].sub("enc:v1:***", out)
    return out

DATA_DIR = Path(os.environ.get("WAKE_SYNC_DATA", "/data"))
PLANS_FILE = DATA_DIR / "plans.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "wakesync.log"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_plans() -> list[dict[str, Any]]:
    _ensure_data_dir()
    if not PLANS_FILE.is_file():
        return []
    with PLANS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_plans(plans: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    with PLANS_FILE.open("w", encoding="utf-8") as f:
        json.dump(plans, f, indent=2, ensure_ascii=False)


def get_plan(plan_id: str) -> dict[str, Any] | None:
    return next((p for p in load_plans() if p.get("id") == plan_id), None)


def update_plan(plan_id: str, **fields: Any) -> None:
    plans = load_plans()
    for p in plans:
        if p.get("id") == plan_id:
            p.update(fields)
            break
    save_plans(plans)


def new_plan_id() -> str:
    return uuid.uuid4().hex[:12]


def new_job_id() -> str:
    """Alias for devices module (SMB device IDs)."""
    return new_plan_id()


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


def append_log(line: str) -> None:
    _ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {redact_secrets(line)}\n")


def read_log_tail(max_lines: int = 120) -> str:
    if not LOG_FILE.is_file():
        return ""
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return redact_secrets("\n".join(lines[-max_lines:]))
