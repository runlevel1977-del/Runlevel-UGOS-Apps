# -*- coding: utf-8 -*-
"""Persistent Stats Hub settings (/data/settings.json)."""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from secret_box import decrypt_secret, encrypt_secret
from store import DATA_DIR, append_log

CONFIG_FILE = DATA_DIR / "settings.json"
_lock = threading.Lock()

INTERVAL_MIN = 15
INTERVAL_MAX = 3600
INTERVAL_CHOICES = (15, 30, 60, 120, 300, 600, 1800)
DEFAULT_DISK_POLL_SEC = 120
DEFAULT_SKIP_STANDBY = True
DEFAULT_UGOS_HOST = "127.0.0.1"
DEFAULT_UGOS_PORT = 9443


def _clamp_interval(v: float) -> int:
    return int(max(INTERVAL_MIN, min(INTERVAL_MAX, round(v))))


def _env_interval() -> int | None:
    raw = os.environ.get("STATS_HUB_DISK_POLL_SEC", "").strip()
    if not raw:
        return None
    try:
        return _clamp_interval(float(raw))
    except ValueError:
        return None


def _env_skip_standby() -> bool | None:
    raw = os.environ.get("STATS_HUB_DISK_SKIP_STANDBY", "").strip().lower()
    if not raw:
        return None
    return raw in ("1", "true", "yes", "on")


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return None
    return raw in ("1", "true", "yes", "on")


def _resolve_ugos_host(raw_host: str) -> str:
    """Map 127.0.0.1/localhost to the NAS when running in Docker bridge."""
    host = (raw_host or "").strip()
    use_local = os.environ.get("UGOS_API_USE_LOCALHOST", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if host and host not in ("127.0.0.1", "localhost"):
        return host
    if use_local:
        return host or "127.0.0.1"
    env_host = os.environ.get("UGOS_API_HOST", "").strip()
    if env_host:
        return env_host
    try:
        from ugos_support import default_ugos_host

        return default_ugos_host() or "172.17.0.1"
    except Exception:
        return "172.17.0.1"


def _normalize_ugos(data: dict[str, Any]) -> dict[str, Any]:
    try:
        port = int(data.get("port", DEFAULT_UGOS_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_UGOS_PORT
    port = max(1, min(65535, port))
    return {
        "enabled": bool(data.get("enabled", True)),
        "host": _resolve_ugos_host(str(data.get("host") or "")),
        "port": port,
        "username": str(data.get("username") or "").strip(),
        "password": decrypt_secret(DATA_DIR, str(data.get("password") or "")),
        "use_https": bool(data.get("use_https", True)),
        "verify_ssl": bool(data.get("verify_ssl", False)),
    }


def _defaults_ugos_from_env() -> dict[str, Any]:
    user = os.environ.get("UGOS_API_USER", "").strip()
    eb = _env_bool("UGOS_API_ENABLED")
    data: dict[str, Any] = {
        "enabled": False,
        "host": _resolve_ugos_host(""),
        "port": DEFAULT_UGOS_PORT,
        "username": "",
        "password": "",
        "use_https": True,
        "verify_ssl": False,
    }
    host = os.environ.get("UGOS_API_HOST", "").strip()
    if host:
        data["host"] = host
    port_raw = os.environ.get("UGOS_API_PORT", "").strip()
    if port_raw:
        try:
            data["port"] = max(1, min(65535, int(port_raw)))
        except ValueError:
            pass
    if user:
        data["username"] = user
    # Do not seed password from environment (plaintext env is a review finding).
    if data["username"] and data["password"]:
        data["enabled"] = True
    if eb is not None:
        data["enabled"] = bool(eb) and bool(data["username"] and data["password"])
    https = _env_bool("UGOS_API_HTTPS")
    if https is not None:
        data["use_https"] = https
    verify = _env_bool("UGOS_API_VERIFY_SSL")
    if verify is not None:
        data["verify_ssl"] = verify
    return _normalize_ugos(data)


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    try:
        interval = _clamp_interval(
            float(data.get("disk_poll_interval_sec", DEFAULT_DISK_POLL_SEC))
        )
    except (TypeError, ValueError):
        interval = DEFAULT_DISK_POLL_SEC
    if interval not in INTERVAL_CHOICES:
        interval = min(INTERVAL_CHOICES, key=lambda c: abs(c - interval))
    skip = data.get("disk_skip_standby", DEFAULT_SKIP_STANDBY)
    ugos_raw = data.get("ugos_api") if isinstance(data.get("ugos_api"), dict) else {}
    return {
        "disk_poll_interval_sec": interval,
        "disk_skip_standby": bool(skip),
        "ugos_api": _normalize_ugos({**_defaults_ugos_from_env(), **ugos_raw}),
    }


def _defaults_from_env() -> dict[str, Any]:
    data: dict[str, Any] = {
        "disk_poll_interval_sec": DEFAULT_DISK_POLL_SEC,
        "disk_skip_standby": DEFAULT_SKIP_STANDBY,
    }
    ei = _env_interval()
    if ei is not None:
        data["disk_poll_interval_sec"] = ei
    es = _env_skip_standby()
    if es is not None:
        data["disk_skip_standby"] = es
    return _normalize(data)


def _load_unlocked() -> dict[str, Any]:
    if CONFIG_FILE.is_file():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return _normalize({**_defaults_from_env(), **raw})
        except (OSError, json.JSONDecodeError):
            pass
    return _defaults_from_env()


def load_settings() -> dict[str, Any]:
    with _lock:
        return _load_unlocked()


def load_ugos_api_settings() -> dict[str, Any]:
    return dict(load_settings().get("ugos_api") or _defaults_ugos_from_env())


def _public_from_cur(cur: dict[str, Any]) -> dict[str, Any]:
    """Public settings view (no password). Caller may already hold ``_lock``."""
    ugos = dict(cur.get("ugos_api") or {})
    pw = str(ugos.get("password") or "")
    ugos_public = {k: v for k, v in ugos.items() if k != "password"}
    ugos_public["password_set"] = bool(pw)
    return {
        "disk_poll_interval_sec": cur["disk_poll_interval_sec"],
        "disk_skip_standby": cur["disk_skip_standby"],
        "ugos_api": ugos_public,
    }


def settings_for_api() -> dict[str, Any]:
    """Public settings view (no password)."""
    return _public_from_cur(load_settings())


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        cur = _load_unlocked()
        if "disk_poll_interval_sec" in updates:
            cur["disk_poll_interval_sec"] = _clamp_interval(
                float(updates["disk_poll_interval_sec"])
            )
            if cur["disk_poll_interval_sec"] not in INTERVAL_CHOICES:
                cur["disk_poll_interval_sec"] = min(
                    INTERVAL_CHOICES, key=lambda c: abs(c - cur["disk_poll_interval_sec"])
                )
        if "disk_skip_standby" in updates:
            cur["disk_skip_standby"] = bool(updates["disk_skip_standby"])
        if "ugos_api" in updates and isinstance(updates["ugos_api"], dict):
            ug = dict(cur.get("ugos_api") or _defaults_ugos_from_env())
            patch = updates["ugos_api"]
            if "enabled" in patch:
                ug["enabled"] = bool(patch["enabled"])
            if "host" in patch:
                ug["host"] = str(patch["host"] or DEFAULT_UGOS_HOST).strip() or DEFAULT_UGOS_HOST
            if "port" in patch:
                try:
                    ug["port"] = max(1, min(65535, int(patch["port"])))
                except (TypeError, ValueError):
                    pass
            if "username" in patch:
                ug["username"] = str(patch["username"] or "").strip()
            if "password" in patch and str(patch["password"] or "").strip():
                ug["password"] = str(patch["password"])
            if "use_https" in patch:
                ug["use_https"] = bool(patch["use_https"])
            if "verify_ssl" in patch:
                ug["verify_ssl"] = bool(patch["verify_ssl"])
            cur["ugos_api"] = _normalize_ugos(ug)
            saved_ug = cur["ugos_api"]
            if saved_ug.get("enabled"):
                if not str(saved_ug.get("username") or "").strip():
                    raise ValueError("username_required")
                if not str(saved_ug.get("password") or "").strip():
                    raise ValueError("password_required")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        disk = json.loads(json.dumps(cur))
        ug_disk = disk.get("ugos_api") or {}
        if ug_disk.get("password"):
            ug_disk["password"] = encrypt_secret(DATA_DIR, str(ug_disk["password"]))
            disk["ugos_api"] = ug_disk
        CONFIG_FILE.write_text(
            json.dumps(disk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        ug = cur.get("ugos_api") or {}
        append_log(
            f"Settings: disk poll {cur['disk_poll_interval_sec']}s, "
            f"skip standby={cur['disk_skip_standby']}, "
            f"UGOS API={'on' if ug.get('enabled') else 'off'}"
        )
        return _public_from_cur(cur)


def get_disk_poll_interval_sec() -> int:
    return int(load_settings()["disk_poll_interval_sec"])


def get_disk_skip_standby() -> bool:
    return bool(load_settings()["disk_skip_standby"])
