# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("LOCK_KEY_DATA", "/data"))
VAULTS_FILE = DATA_DIR / "vaults.json"
JOBS_FILE = DATA_DIR / "jobs.json"
LOG_FILE = DATA_DIR / "lockkey.log"
META_FILE = DATA_DIR / "meta.json"
_jobs_lock = threading.Lock()


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_vaults() -> list[dict[str, Any]]:
    _ensure_data_dir()
    if not VAULTS_FILE.is_file():
        return []
    with VAULTS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_vaults(vaults: list[dict[str, Any]]) -> None:
    _ensure_data_dir()
    with VAULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(vaults, f, indent=2, ensure_ascii=False)


def get_vault(vault_id: str) -> dict[str, Any] | None:
    return next((v for v in load_vaults() if v.get("id") == vault_id), None)


def upsert_vault(vault: dict[str, Any]) -> None:
    vaults = load_vaults()
    vid = vault.get("id")
    found = False
    for i, row in enumerate(vaults):
        if row.get("id") == vid:
            vaults[i] = vault
            found = True
            break
    if not found:
        vaults.append(vault)
    save_vaults(vaults)


def delete_vault(vault_id: str) -> bool:
    vaults = [v for v in load_vaults() if v.get("id") != vault_id]
    if len(vaults) == len(load_vaults()):
        return False
    save_vaults(vaults)
    return True


def load_meta() -> dict[str, Any]:
    _ensure_data_dir()
    if not META_FILE.is_file():
        return {}
    try:
        with META_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_meta(meta: dict[str, Any]) -> None:
    _ensure_data_dir()
    with META_FILE.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def load_deleted_vault_ids() -> set[str]:
    raw = load_meta().get("deleted_vault_ids") or []
    if not isinstance(raw, list):
        return set()
    return {str(x).strip() for x in raw if str(x).strip()}


def mark_vault_deleted(vault_id: str) -> None:
    vid = (vault_id or "").strip()
    if not vid:
        return
    meta = load_meta()
    ids = [x for x in (meta.get("deleted_vault_ids") or []) if str(x).strip()]
    if vid not in ids:
        ids.append(vid)
    meta["deleted_vault_ids"] = ids[-200:]
    save_meta(meta)


def is_vault_deleted(vault_id: str) -> bool:
    return (vault_id or "").strip() in load_deleted_vault_ids()


def new_vault_id() -> str:
    return uuid.uuid4().hex[:12]


def load_jobs() -> dict[str, Any]:
    _ensure_data_dir()
    if not JOBS_FILE.is_file():
        return {}
    try:
        with JOBS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_jobs(jobs: dict[str, Any]) -> None:
    _ensure_data_dir()
    tmp = JOBS_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    tmp.replace(JOBS_FILE)


def set_job(job_id: str, **fields: Any) -> None:
    with _jobs_lock:
        jobs = load_jobs()
        row = jobs.get(job_id, {})
        row.update(fields)
        jobs[job_id] = row
        save_jobs(jobs)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        return load_jobs().get(job_id)


def append_log(line: str) -> None:
    _ensure_data_dir()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")


def read_log_tail(max_lines: int = 120) -> str:
    if not LOG_FILE.is_file():
        return ""
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])
