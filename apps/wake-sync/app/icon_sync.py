# -*- coding: utf-8 -*-
"""Best-effort: package icon -> UGOS App Center static path."""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def _log(msg: str) -> None:
    try:
        from store import append_log

        append_log(msg)
    except Exception:
        print(msg, flush=True)


def sync_appcenter_icon(app_id: str) -> bool:
    env_id = (os.environ.get("UGOS_APP_ID") or app_id or "").strip()
    if not env_id:
        return False

    src_candidates: list[Path] = []
    pkg_mount = (os.environ.get("UGOS_PKG_DIR") or "/pkg").strip()
    if pkg_mount:
        src_candidates.append(Path(pkg_mount) / "icon.png")
    src_candidates.extend(
        [
            Path("/host/icon.png"),
            Path(f"/var/packages/{env_id}/icon.png"),
        ]
    )

    src = next((p for p in src_candidates if p.is_file()), None)
    if src is None:
        _log(f"ICON sync: no source icon for {env_id}")
        return False

    dst_candidates = [
        Path(f"/static/icons/{env_id}.png"),
        Path(f"/ugreen/static/icons/{env_id}.png"),
    ]

    ok = False
    for dst in dst_candidates:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            os.chmod(dst, 0o644)
            _log(f"ICON sync OK: {src} -> {dst}")
            ok = True
        except OSError as ex:
            _log(f"ICON sync fail {dst}: {ex}")
    return ok
