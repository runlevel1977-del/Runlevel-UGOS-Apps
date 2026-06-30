# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from devices import endpoint_uses_smb, rclone_remote_url
from path_filters import TRANSFER_EXCLUDE_GLOBS
from store import append_log


def _rclone_exclude_args() -> list[str]:
    args: list[str] = []
    for pat in TRANSFER_EXCLUDE_GLOBS:
        args.extend(["--exclude", pat])
    return args


def _rclone_smb_compat() -> list[str]:
    return ["--disable", "OpenWriterAt,OpenChunkWriter"]


def run_sync(source_ep: dict[str, Any], dest_ep: dict[str, Any]) -> tuple[bool, str, dict]:
    """One-way sync: local NAS → SMB target (e.g. QNAP)."""
    try:
        src_url = rclone_remote_url(source_ep)
        dst_url = rclone_remote_url(dest_ep)
    except ValueError as ex:
        return False, "path_error", {"tail": str(ex)}

    src = Path(src_url)
    if not src.is_dir():
        return False, "source_missing", {"source": src_url}

    uses_smb = endpoint_uses_smb(dest_ep)
    cmd = [
        "rclone",
        "sync",
        src_url,
        dst_url,
        "--create-empty-src-dirs",
        "--progress",
        "--stats-one-line",
        "--stats",
        "30s",
        "--timeout",
        "12h",
        "--contimeout",
        "5m",
        "--retries",
        "5",
        "--low-level-retries",
        "10",
        *(_rclone_smb_compat() if uses_smb else []),
        *_rclone_exclude_args(),
    ]
    append_log(f"SYNC {' '.join(cmd[:6])}… → {dst_url[:100]}…")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=86400,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "timeout", {}

    output = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-25:])
    if proc.returncode != 0:
        append_log(f"SYNC FAIL exit {proc.returncode}\n{tail[-800:]}")
        return False, "sync_error", {"exit_code": proc.returncode, "tail": tail}

    append_log("SYNC OK")
    return True, "ok", {"tail": tail[-1200:]}
