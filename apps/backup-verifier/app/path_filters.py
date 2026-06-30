# -*- coding: utf-8 -*-
"""System/hidden paths excluded from verification."""
from __future__ import annotations

import re

_SMB_LS_LINE = re.compile(r"^\s+(.+?)\s+([ADHRSNT]+)\s+(\d+)\s", re.IGNORECASE)

# Alias for shared device/rclone code (same rules as Transfer Hub).
TRANSFER_EXCLUDE_GLOBS = VERIFY_EXCLUDE_GLOBS = (
    "@*/**",
    "**/@*/**",
    "overlay2/**",
    "**/overlay2/**",
    "**/merged/proc/**",
    "**/proc/**",
    "**/sys/**",
    "**/dev/**",
    "lost+found/**",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "#recycle/**",
    "**/#recycle/**",
)


def is_hidden_name(name: str) -> bool:
    if not name or name in (".", ".."):
        return True
    return name.startswith("@")


def parse_smbclient_ls_line(line: str) -> tuple[str, str] | None:
    raw = line.rstrip()
    if not raw.strip():
        return None
    match = _SMB_LS_LINE.match(raw)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).upper()


def rsync_exclude_args() -> list[str]:
    args: list[str] = []
    for pat in VERIFY_EXCLUDE_GLOBS:
        args.extend(["--exclude", pat])
    return args
