# -*- coding: utf-8 -*-
"""Hidden @-folders and transfer excludes (UGOS/Synology system dirs)."""
from __future__ import annotations

import re

# smbclient ls: "  USB_SSD Safe                       D        0  ..."
_SMB_LS_LINE = re.compile(r"^\s+(.+?)\s+([ADHRSNT]+)\s+(\d+)\s", re.IGNORECASE)

# Never show in folder picker; never copy (rclone/rsync).
TRANSFER_EXCLUDE_GLOBS = (
    "@*/**",
    "**/@*/**",
    "@**",
    "overlay2/**",
    "**/overlay2/**",
    "**/merged/proc/**",
    "**/proc/**",
    "**/sys/**",
    "**/dev/**",
    "**/*.partial*",
    "**/pagemap*",
    ".docker/**",
    "lost+found/**",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "#recycle/**",
    "**/#recycle/**",
)


def is_hidden_name(name: str) -> bool:
    """True if folder/file must not appear in picker or be transferred."""
    if not name or name in (".", ".."):
        return True
    return name.startswith("@")


def parse_smbclient_ls_line(line: str) -> tuple[str, str] | None:
    """Parse smbclient ls line → (name, attributes) or None."""
    raw = line.rstrip()
    if not raw.strip():
        return None
    match = _SMB_LS_LINE.match(raw)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).upper()
