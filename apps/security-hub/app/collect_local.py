# -*- coding: utf-8 -*-
"""Bash-Ausführung für NAS-gemountete Log-Pfade."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from access_collect import nas_collect_shell, nas_collect_shell_live

HOST_VAR_LOG = os.environ.get("HOST_VAR_LOG", "/host/var/log")
HOST_UGREEN_LOG = os.environ.get("HOST_UGREEN_LOG", "/host/ugreen/log")


def probe_mounts() -> list[str]:
    issues: list[str] = []
    for label, path in (("HOST_VAR_LOG", HOST_VAR_LOG), ("HOST_UGREEN_LOG", HOST_UGREEN_LOG)):
        if not Path(path).is_dir():
            issues.append(f"{label} not mounted ({path})")
    return issues


def run_bash(script: str, *, timeout: int = 120) -> tuple[str, str]:
    proc = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        errors="replace",
    )
    out = proc.stdout or ""
    err = (proc.stderr or "").strip()
    if proc.returncode != 0 and err:
        out = out + ("\n# stderr: " + err if out else "# stderr: " + err)
    return out, err


def local_collect_shell(*, days: int = 30) -> str:
    return nas_collect_shell(days=days)


def local_collect_shell_live(*, since_minutes: int = 5) -> str:
    return nas_collect_shell_live(since_minutes=since_minutes)
