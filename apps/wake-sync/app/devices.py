# -*- coding: utf-8 -*-
"""Saved endpoints (this NAS, SMB PCs/other NAS) and path resolution."""
from __future__ import annotations

import json
import os
import subprocess
from os import scandir
import tempfile
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from path_filters import is_hidden_name, parse_smbclient_ls_line
from smb_cache import (
    build_smb_cache,
    cache_key,
    cache_summary,
    clear_build_status,
    delete_smb_cache,
    dirs_from_cache,
    get_build_status,
    load_smb_cache,
    shares_from_cache,
    start_smb_cache_build,
    update_cache_dirs,
    update_cache_shares,
)
from store import DATA_DIR, append_log, new_job_id
from volumes import list_volumes, normalize_volume_id, resolve_local_path, volume_label

DEVICES_FILE = DATA_DIR / "devices.json"
LOCAL_ID = "local"
NAS_MOUNT = os.environ.get("NAS_MOUNT", "/mnt/nas")
WORK_MOUNT = Path("/mnt/work")


def _ensure() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORK_MOUNT.mkdir(parents=True, exist_ok=True)


def load_devices() -> list[dict[str, Any]]:
    _ensure()
    if not DEVICES_FILE.is_file():
        return [_default_local()]
    with DEVICES_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return [_default_local()]
    if not any(d.get("id") == LOCAL_ID for d in data):
        data.insert(0, _default_local())
    return data


def save_devices(devices: list[dict[str, Any]]) -> None:
    _ensure()
    with DEVICES_FILE.open("w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)


def _default_local() -> dict[str, Any]:
    return {
        "id": LOCAL_ID,
        "name": "Dieses NAS",
        "type": "local",
        "host": "",
        "username": "",
        "password": "",
    }


def get_device(device_id: str) -> dict[str, Any] | None:
    return next((d for d in load_devices() if d.get("id") == device_id), None)


def add_smb_device(
    name: str, host: str, username: str, password: str, mac: str = ""
) -> dict[str, Any]:
    host = host.strip()
    dev = {
        "id": "dev_" + new_job_id(),
        "name": (name or host).strip(),
        "type": "smb",
        "host": host,
        "mac": (mac or "").strip(),
        "username": username,
        "password": password,
    }
    devices = load_devices()
    devices.append(dev)
    save_devices(devices)
    return dev


def delete_device(device_id: str) -> bool:
    if device_id == LOCAL_ID:
        return False
    devices = [d for d in load_devices() if d.get("id") != device_id]
    save_devices(devices)
    delete_smb_cache(device_id)
    return True


def refresh_device_folder_cache(device_id: str) -> tuple[bool, str]:
    device = get_device(device_id)
    if not device or device.get("type") != "smb":
        return False, "device not found"
    started = start_smb_cache_build(device, _list_smb_shares_live, _list_smb_dirs_live)
    if not started:
        return False, "already building"
    return True, "started"


def device_public_row(device: dict[str, Any]) -> dict[str, Any]:
    row = {**device}
    if device.get("type") == "smb":
        row["folder_cache"] = cache_summary(device["id"])
    if "password" in row:
        row["password"] = "***"
    return row


def update_smb_device(device_id: str, **fields: Any) -> dict[str, Any] | None:
    if device_id == LOCAL_ID:
        return None
    devices = load_devices()
    for d in devices:
        if d.get("id") != device_id or d.get("type") != "smb":
            continue
        if "name" in fields:
            d["name"] = (fields["name"] or d.get("host") or "").strip()
        if "mac" in fields:
            d["mac"] = (fields["mac"] or "").strip()
        save_devices(devices)
        return d
    return None


def _smb_cred_args(username: str, password: str) -> list[str]:
    if username:
        return ["-U", f"{username}%{password}"]
    return ["-N"]


def test_smb(host: str, username: str, password: str) -> tuple[bool, str]:
    cmd = ["smbclient", "-L", f"//{host}", *_smb_cred_args(username, password), "-g"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
            return False, err[0] if err else "SMB-Verbindung fehlgeschlagen"
        return True, "Verbunden"
    except Exception as e:
        return False, str(e)


def _parse_smb_share_lines(stdout: str) -> list[dict[str, str]]:
    shares: list[dict[str, str]] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("Disk|") and "|" in line:
            parts = line.split("|")
            if len(parts) >= 2 and parts[1] not in ("IPC$", "print$"):
                shares.append({"name": parts[1], "path": parts[1], "kind": "share"})
    return sorted(shares, key=lambda x: x["name"].lower())


def _parse_smb_dir_lines(stdout: str, subpath: str) -> list[dict[str, str]]:
    sub = (subpath or "").strip().strip("/").replace("\\", "/")
    entries: list[dict[str, str]] = []
    for line in (stdout or "").splitlines():
        parsed = parse_smbclient_ls_line(line)
        if not parsed:
            continue
        name, attrs = parsed
        if name in (".", "..") or is_hidden_name(name):
            continue
        if "D" not in attrs:
            continue
        child = f"{sub}/{name}".strip("/") if sub else name
        entries.append({"name": name, "path": child, "kind": "dir"})
    return sorted(entries, key=lambda x: x["name"].lower())


def _list_smb_shares_live(device: dict[str, Any]) -> tuple[list[dict[str, str]], bool]:
    host = device["host"]
    cmd = [
        "smbclient",
        "-L",
        f"//{host}",
        *_smb_cred_args(device.get("username", ""), device.get("password", "")),
        "-g",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception:
        return [], False
    if proc.returncode != 0:
        return [], False
    return _parse_smb_share_lines(proc.stdout or ""), True


def _list_smb_dirs_live(
    device: dict[str, Any], share: str, subpath: str
) -> tuple[list[dict[str, str]], bool]:
    sub = (subpath or "").strip().strip("/").replace("\\", "/")
    cd = f'cd "{sub}";' if sub else ""
    cmd = [
        "smbclient",
        f"//{device['host']}/{share}",
        *_smb_cred_args(device.get("username", ""), device.get("password", "")),
        "-c",
        f"{cd} ls",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception:
        return [], False
    if proc.returncode != 0:
        return [], False
    return _parse_smb_dir_lines(proc.stdout or "", sub), True


def list_smb_shares(device: dict[str, Any]) -> list[dict[str, str]]:
    shares, _ = _list_smb_shares_live(device)
    return shares


def _smb_list_dirs(device: dict[str, Any], share: str, subpath: str) -> list[dict[str, str]]:
    dirs, _ = _list_smb_dirs_live(device, share, subpath)
    return dirs


def _browse_smb(
    device_id: str, device: dict[str, Any], share: str, path: str, lng: str
) -> dict[str, Any]:
    from i18n import t

    cache = load_smb_cache(device_id)
    cached = False
    hint = ""

    if not share:
        entries, ok = _list_smb_shares_live(device)
        if ok:
            update_cache_shares(device_id, [e["name"] for e in entries])
            if not entries:
                hint = t("browse.no_subdirs", lng)
        elif cache and cache.get("shares") is not None:
            entries = shares_from_cache(cache)
            cached = True
            hint = t("browse.cached_offline", lng)
        else:
            return {"ok": False, "error": t("err.nas_offline_no_cache", lng)}
    else:
        entries, ok = _list_smb_dirs_live(device, share, path or "")
        if ok:
            update_cache_dirs(device_id, share, path or "", [e["name"] for e in entries])
            if not entries and not (path or ""):
                hint = t("browse.no_subdirs", lng)
        elif cache is not None:
            key = cache_key(share, path or "")
            if key in (cache.get("dirs") or {}):
                entries = dirs_from_cache(cache, share, path or "")
                cached = True
                hint = t("browse.cached_offline", lng)
                if not entries:
                    hint = t("browse.cached_leaf", lng)
            else:
                return {"ok": False, "error": t("err.cache_path_missing", lng)}
        else:
            return {"ok": False, "error": t("err.nas_offline_no_cache", lng)}

    return {
        "ok": True,
        "device_id": device_id,
        "share": share,
        "path": path or "",
        "parent": _parent_path(path or ""),
        "entries": entries,
        "hint": hint,
        "cached": cached,
    }


def list_local_volume_picker() -> list[dict[str, str]]:
    from i18n import get_lang, t

    lng = get_lang()
    return [
        {
            "name": t("picker.open_volume_fmt", lng, label=v["label"]),
            "path": "",
            "kind": "volume",
            "volume": v["id"],
        }
        for v in list_volumes()
    ]


def list_local_dirs(volume_id: str, subpath: str) -> list[dict[str, str]]:
    try:
        target = resolve_local_path(volume_id, subpath)
    except ValueError:
        return []
    if not target.is_dir():
        return []
    rel = (subpath or "").strip().strip("/")
    entries: list[dict[str, str]] = []
    try:
        with scandir(target) as it:
            for entry in it:
                name = entry.name
                if is_hidden_name(name):
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if not is_dir:
                    continue
                p = f"{rel}/{name}".strip("/") if rel else name
                entries.append({"name": name, "path": p, "kind": "dir"})
    except OSError as e:
        append_log(f"Ordnerliste {target}: {e}")
    if not entries:
        try:
            proc = subprocess.run(
                ["ls", "-1A", str(target)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                for name in (proc.stdout or "").splitlines():
                    if is_hidden_name(name):
                        continue
                    full = target / name
                    if full.is_dir():
                        p = f"{rel}/{name}".strip("/") if rel else name
                        entries.append({"name": name, "path": p, "kind": "dir"})
        except OSError as e:
            append_log(f"ls {target}: {e}")
    return sorted(entries, key=lambda x: x["name"].lower())


def _browse_local(volume: str, path: str) -> dict[str, Any]:
    from i18n import get_lang, t

    lng = get_lang()
    vol = normalize_volume_id(volume)
    rel = path or ""
    entries = list_local_dirs(vol, rel)
    hint = ""
    if not entries and not rel:
        hint = t("browse.no_subdirs", lng)
    return {
        "ok": True,
        "device_id": LOCAL_ID,
        "share": "",
        "volume": vol,
        "path": rel,
        "parent": _parent_path(rel) if rel else "",
        "entries": entries,
        "hint": hint,
    }


def browse(device_id: str, path: str = "", share: str = "", volume: str = "") -> dict[str, Any]:
    device = get_device(device_id)
    from i18n import get_lang, t

    lng = get_lang()
    if not device:
        return {"ok": False, "error": t("err.device_not_found", lng)}
    if device.get("type") == "local":
        if not volume:
            vols = list_volumes()
            if len(vols) == 1:
                return _browse_local(vols[0]["id"], path or "")
            return {
                "ok": True,
                "device_id": LOCAL_ID,
                "share": "",
                "volume": "",
                "path": "",
                "parent": "",
                "entries": list_local_volume_picker(),
                "hint": t("browse.pick_volume", lng),
            }
        return _browse_local(volume, path or "")
    if device.get("type") == "smb":
        return _browse_smb(device_id, device, share, path or "", lng)
    return {"ok": False, "error": t("err.unknown_device_type", lng)}


def _parent_path(path: str) -> str:
    p = (path or "").strip().strip("/")
    if not p:
        return ""
    parts = p.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def _rclone_obscure_password(password: str) -> str:
    if not password:
        return ""
    proc = subprocess.run(
        ["rclone", "obscure", password],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if proc.returncode != 0:
        return password
    return (proc.stdout or "").strip()


def _conn_value(value: str) -> str:
    """Quote connection-string values that contain , or =."""
    if any(c in value for c in ",='"):
        escaped = value.replace("'", "\\'")
        return f"'{escaped}'"
    return value


def rclone_remote_url(ep: dict[str, Any]) -> str:
    """Local filesystem path or rclone :smb,...:share/path spec (no CIFS mount)."""
    device = get_device(ep.get("device_id", LOCAL_ID))
    if not device:
        raise ValueError("Gerät nicht gefunden")
    if device.get("type") == "local":
        vol = normalize_volume_id(ep.get("volume"))
        return str(resolve_local_path(vol, ep.get("path") or "").resolve())
    if device.get("type") == "smb":
        share = (ep.get("share") or "").strip()
        if not share:
            raise ValueError("SMB-Freigabe fehlt")
        host = _conn_value(device["host"].strip())
        user = _conn_value((device.get("username") or "").strip())
        pw = _rclone_obscure_password(device.get("password") or "")
        sub = (ep.get("path") or "").strip().strip("/")
        remote_path = f"{share}/{sub}" if sub else share
        domain = _conn_value((device.get("domain") or "WORKGROUP").strip())
        return (
            f":smb,host={host},user={user},pass={pw},domain={domain},"
            f"case_insensitive=true,idle_timeout=0:"
            f"{remote_path}"
        )
    raise ValueError("Unbekannter Gerätetyp")


def smb_delete_source_tree(
    device: dict[str, Any], share: str, subpath: str
) -> tuple[bool, str]:
    """Delete transferred files on SMB share (fallback when rclone delete fails)."""
    sub = (subpath or "").strip().strip("/")
    cd = f'cd "{sub}";' if sub else ""
    cmd = [
        "smbclient",
        f"//{device['host']}/{share}",
        *_smb_cred_args(device.get("username", ""), device.get("password", "")),
        "-c",
        f"{cd}recurse ON; prompt OFF; mdelete *",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        out = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode != 0:
            tail = "\n".join(out.splitlines()[-8:])
            return False, tail or f"smbclient exit {proc.returncode}"
        for _ in range(8):
            rmdir = [
                "smbclient",
                f"//{device['host']}/{share}",
                *_smb_cred_args(device.get("username", ""), device.get("password", "")),
                "-c",
                f"{cd}recurse ON; prompt OFF; rmdir *",
            ]
            proc2 = subprocess.run(rmdir, capture_output=True, text=True, timeout=120)
            if proc2.returncode != 0:
                break
        return True, "smbclient cleanup ok"
    except Exception as e:
        return False, str(e)


def endpoint_uses_smb(ep: dict[str, Any]) -> bool:
    device = get_device(ep.get("device_id", LOCAL_ID))
    return bool(device and device.get("type") == "smb")


def endpoint_label(ep: dict[str, Any]) -> str:
    from i18n import get_lang, t

    lng = get_lang()
    dev = get_device(ep.get("device_id", LOCAL_ID))
    if dev and dev.get("id") == LOCAL_ID:
        name = t("device.this_nas", lng)
    else:
        name = dev.get("name", "?") if dev else "?"
    if dev and dev.get("type") == "smb":
        share = ep.get("share") or ""
        sub = (ep.get("path") or "").strip().strip("/")
        if not share:
            return f"{name}:/{sub + ' (Freigabe fehlt!)' if sub else '?'}"
        tail = f"{share}/{sub}".strip("/") if sub else share
        return f"{name}:/{tail}"
    vol = normalize_volume_id(ep.get("volume"))
    sub = (ep.get("path") or "").strip().strip("/")
    vlabel = volume_label(vol)
    if sub:
        return f"{name} · {vlabel}:/{sub}"
    return f"{name} · {vlabel}{t('volume.whole', lng)}"


@contextmanager
def resolved_mount(ep: dict[str, Any]) -> Iterator[tuple[str, str | None]]:
    """Yield (local_path_with_trailing_slash, cleanup_mount_or_none)."""
    device = get_device(ep.get("device_id", LOCAL_ID))
    if not device:
        raise ValueError("Gerät nicht gefunden")
    if device.get("type") == "local":
        vol = normalize_volume_id(ep.get("volume"))
        root = resolve_local_path(vol, ep.get("path") or "")
        yield str(root).rstrip("/") + "/", None
        return
    if device.get("type") == "smb":
        share = ep.get("share") or ""
        if not share:
            raise ValueError("SMB-Freigabe fehlt")
        sub = (ep.get("path") or "").strip().strip("/")
        mount_point = WORK_MOUNT / str(ep.get("device_id", "x"))
        mount_point.mkdir(parents=True, exist_ok=True)
        cred = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".cred")
        try:
            cred.write(f"username={device.get('username','')}\n")
            cred.write(f"password={device.get('password','')}\n")
            domain = (device.get("domain") or "WORKGROUP").strip()
            if domain:
                cred.write(f"domain={domain}\n")
            cred.close()
            mount_opts = (
                f"credentials={cred.name},uid=0,gid=0,"
                f"file_mode=0644,dir_mode=0755,vers=3.0,sec=ntlmssp,noserverino"
            )
            proc = subprocess.run(
                [
                    "mount",
                    "-t",
                    "cifs",
                    f"//{device['host']}/{share}",
                    str(mount_point),
                    "-o",
                    mount_opts,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip()
                raise OSError(err or f"mount cifs exit {proc.returncode}")
            target = mount_point / sub if sub else mount_point
            if not target.is_dir():
                raise OSError(f"Zielordner nicht gefunden: {target}")
            try:
                yield str(target).rstrip("/") + "/", str(mount_point)
            finally:
                subprocess.run(["umount", "-l", str(mount_point)], capture_output=True, timeout=30)
        finally:
            try:
                os.unlink(cred.name)
            except OSError:
                pass
        return
    raise ValueError("Unbekannter Gerätetyp")
