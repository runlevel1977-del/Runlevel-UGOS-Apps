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
    return _copy_icon_src(src, env_id)


def sync_package_icon(app_id: str) -> bool:
    src = Path(f"/var/packages/{app_id}/icon.png")
    if not src.is_file():
        return False
    return _copy_icon_src(src, app_id)


def sync_all_runlevel_icons() -> int:
    """Copy icons for installed com.runlevel.* apps into UGOS static folder."""
    count = 0
    pkg_root = Path("/var/packages")
    if not pkg_root.is_dir():
        return 0
    for pkg in sorted(pkg_root.glob("com.runlevel.*")):
        if not pkg.is_dir():
            continue
        app_id = pkg.name
        if sync_package_icon(app_id):
            count += 1
    return count


def _copy_icon_src(src: Path | None, app_id: str) -> bool:
    if src is None or not src.is_file():
        append_log(f"ICON sync: no source for {app_id}")
        return False
    ok = False
    for dst in (Path(f"/static/icons/{app_id}.png"), Path(f"/ugreen/static/icons/{app_id}.png")):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            os.chmod(dst, 0o644)
            append_log(f"ICON sync OK: {src} -> {dst}")
            ok = True
        except OSError as ex:
            append_log(f"ICON sync fail {dst}: {ex}")
    return ok
