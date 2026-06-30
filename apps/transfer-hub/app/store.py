# -*- coding: utf-8 -*-
"""Profile persistence under /data."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("TRANSFER_HUB_DATA", "/data"))
PROFILES_FILE = DATA_DIR / "profiles.json"
LOG_FILE = DATA_DIR / "hub.log"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_profiles() -> list[dict[str, Any]]:
    _ensure_data_dir()
    if not PROFILES_FILE.is_file():
        return []
    with PROFILES_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_profiles(profiles: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    with PROFILES_FILE.open("w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def append_log(line: str) -> None:
    _ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")


def read_log_tail(max_lines: int = 80) -> str:
    if not LOG_FILE.is_file():
        return ""
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def new_profile_id() -> str:
    return uuid.uuid4().hex[:12]


def _ep_key(ep: Any) -> str:
    if isinstance(ep, dict):
        return (
            f"{ep.get('device_id')}|{ep.get('volume') or ''}|"
            f"{ep.get('share')}|{ep.get('path')}"
        )
    return str(ep or "")


def find_reverse_conflict(
    profiles: list[dict[str, Any]],
    source: Any,
    dest: Any,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    """Warn if an active auto job would run opposite on the same paths."""
    sk, dk = _ep_key(source), _ep_key(dest)
    for p in profiles:
        if exclude_id and p.get("id") == exclude_id:
            continue
        if _ep_key(p.get("source")) == dk and _ep_key(p.get("dest")) == sk:
            if p.get("auto_sync"):
                return p
    return None
