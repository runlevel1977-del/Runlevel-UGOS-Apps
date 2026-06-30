# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
from pathlib import Path

from store import append_log


def sync_appcenter_icon(app_id: str) -> bool:
    env_id = (os.environ.get("UGOS_APP_ID") or app_id or "").strip()
    if not env_id:
        return False
    pkg = (os.environ.get("UGOS_PKG_DIR") or "/pkg").strip()
    src = next(
        (p for p in (Path(pkg) / "icon.png", Path(f"/var/packages/{env_id}/icon.png")) if p.is_file()),
        None,
    )
    if src is None:
        append_log(f"ICON sync: no source for {env_id}")
        return False
    ok = False
    for dst in (Path(f"/static/icons/{env_id}.png"), Path(f"/ugreen/static/icons/{env_id}.png")):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            os.chmod(dst, 0o644)
            append_log(f"ICON sync OK: {src} -> {dst}")
            ok = True
        except OSError as ex:
            append_log(f"ICON sync fail {dst}: {ex}")
    return ok
