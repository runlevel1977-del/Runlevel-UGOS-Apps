# -*- coding: utf-8 -*-
"""Saved endpoints (this NAS, SMB PCs/other NAS) and path resolution."""
from __future__ import annotations

import json
import os
import re
import subprocess
from os import scandir
import tempfile
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from path_filters import is_hidden_name, parse_smbclient_ls_line
from secret_box import decrypt_secret, encrypt_secret
from store import DATA_DIR, append_log, new_profile_id
from volumes import list_volumes, normalize_volume_id, resolve_local_path, volume_label

DEVICES_FILE = DATA_DIR / "devices.json"
LOCAL_ID = "local"
NAS_MOUNT = os.environ.get("NAS_MOUNT", "/mnt/nas")
WORK_MOUNT = Path("/mnt/work")
_HOST_RE = re.compile(
    r"^(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"|(?:\d{1,3}\.){3}\d{1,3})$"
)
_SHARE_RE = re.compile(r"^[^\\/\[\]:;|<>+?=*\x00-\x1f\"'`$]{1,80}$")
_USER_RE = re.compile(r"^[^%\r\n\"'`$]{0,128}$")


def validate_smb_host(host: str) -> str:
    h = (host or "").strip()
    if not h or not _HOST_RE.match(h) or "/" in h:
        raise ValueError("Invalid host")
    return h


def validate_smb_share(share: str) -> str:
    s = (share or "").strip().strip("/").replace("\\", "/")
    if not s or not _SHARE_RE.match(s) or ".." in s:
        raise ValueError("Invalid share")
    return s


def validate_smb_relpath(path: str) -> str:
    rel = (path or "").strip().strip("/").replace("\\", "/")
    if not rel:
        return ""
    if any(p in (".", "..") for p in rel.split("/")):
        raise ValueError("Invalid path")
    if any(c in rel for c in '\\:;|<>?*`"\'$\n\r'):
        raise ValueError("Invalid path")
    return rel


def validate_smb_username(username: str) -> str:
    u = str(username or "")
    if not _USER_RE.match(u):
        raise ValueError("Invalid username")
    return u


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
    if any(
        d.get("type") == "smb"
        and d.get("password")
        and not str(d.get("password") or "").startswith("enc:v1:")
        for d in data
    ):
        save_devices(data)
        with DEVICES_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return [_default_local()]
    return data


def save_devices(devices: list[dict[str, Any]]) -> None:
    _ensure()
    out: list[dict[str, Any]] = []
    for raw in devices:
        row = dict(raw)
        if row.get("type") == "smb":
            row["password"] = encrypt_secret(DATA_DIR, str(row.get("password") or ""))
        out.append(row)
    with DEVICES_FILE.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


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
    found = next((d for d in load_devices() if d.get("id") == device_id), None)
    if not found:
        return None
    row = dict(found)
    if row.get("type") == "smb":
        row["password"] = decrypt_secret(DATA_DIR, str(row.get("password") or ""))
    return row


def device_public_row(device: dict[str, Any]) -> dict[str, Any]:
    row = {k: v for k, v in device.items() if k != "password"}
    if device.get("type") == "smb":
        row["password_set"] = bool(device.get("password"))
    return row


def add_smb_device(name: str, host: str, username: str, password: str) -> dict[str, Any]:
    host = validate_smb_host(host)
    username = validate_smb_username(username)
    dev = {
        "id": "dev_" + new_profile_id(),
        "name": (name or host).strip(),
        "type": "smb",
        "host": host,
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
    return True


def _smb_cred_args(username: str, password: str) -> list[str]:
    if username:
        return ["-U", f"{username}%{password}"]
    return ["-N"]


def test_smb(host: str, username: str, password: str) -> tuple[bool, str]:
    from store import redact_secrets

    try:
        host = validate_smb_host(host)
        username = validate_smb_username(username)
    except ValueError as ex:
        return False, str(ex)
    cmd = ["smbclient", "-L", f"//{host}", *_smb_cred_args(username, password), "-g"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
            msg = err[0] if err else "SMB-Verbindung fehlgeschlagen"
            return False, redact_secrets(msg)
        return True, "Verbunden"
    except Exception as e:
        return False, redact_secrets(str(e))


def is_windows_admin_share(name: str) -> bool:
    """True for Windows hidden/admin shares (ADMIN$, C$, IPC$, …)."""
    n = (name or "").strip()
    if not n:
        return True
    if n in ("IPC$", "print$", "ADMIN$"):
        return True
    return n.endswith("$")


def list_smb_shares(device: dict[str, Any]) -> list[dict[str, str]]:
    try:
        host = validate_smb_host(str(device.get("host") or ""))
        username = validate_smb_username(str(device.get("username") or ""))
    except ValueError:
        return []
    cmd = [
        "smbclient",
        "-L",
        f"//{host}",
        *_smb_cred_args(username, device.get("password", "")),
        "-g",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    shares: list[dict[str, str]] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("Disk|") and "|" in line:
            parts = line.split("|")
            if len(parts) >= 2 and not is_windows_admin_share(parts[1]):
                shares.append({"name": parts[1], "path": parts[1], "kind": "share"})
    return sorted(shares, key=lambda x: x["name"].lower())


def _smb_list_dirs(device: dict[str, Any], share: str, subpath: str) -> list[dict[str, str]]:
    try:
        host = validate_smb_host(str(device.get("host") or ""))
        share = validate_smb_share(share)
        sub = validate_smb_relpath(subpath)
        username = validate_smb_username(str(device.get("username") or ""))
    except ValueError:
        return []
    cmd = [
        "smbclient",
        f"//{host}/{share}",
        *_smb_cred_args(username, device.get("password", "")),
        "-c",
        "ls",
    ]
    if sub:
        cmd.extend(["-D", sub])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    entries: list[dict[str, str]] = []
    if proc.returncode != 0:
        return entries
    for line in (proc.stdout or "").splitlines():
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
    try:
        real_target = target.resolve()
        mount = resolve_local_path(volume_id, "").resolve()
        if not str(real_target).startswith(str(mount)):
            append_log(f"browse: path traversal rejected: {target}")
            return []
    except (OSError, ValueError):
        return []
    target = real_target
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
        if not share:
            return {
                "ok": True,
                "device_id": device_id,
                "share": "",
                "path": "",
                "parent": "",
                "entries": list_smb_shares(device),
            }
        try:
            share = validate_smb_share(share)
            path = validate_smb_relpath(path or "")
        except ValueError:
            return {"ok": False, "error": t("err.generic", lng)}
        return {
            "ok": True,
            "device_id": device_id,
            "share": share,
            "path": path or "",
            "parent": _parent_path(path or ""),
            "entries": _smb_list_dirs(device, share, path or ""),
        }
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
        share = validate_smb_share(ep.get("share") or "")
        host = _conn_value(validate_smb_host(str(device.get("host") or "")))
        user = _conn_value(validate_smb_username(str(device.get("username") or "")))
        pw = _rclone_obscure_password(device.get("password") or "")
        sub = validate_smb_relpath(ep.get("path") or "")
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
    try:
        host = validate_smb_host(str(device.get("host") or ""))
        share = validate_smb_share(share)
        sub = validate_smb_relpath(subpath)
        username = validate_smb_username(str(device.get("username") or ""))
    except ValueError as ex:
        return False, str(ex)
    creds = _smb_cred_args(username, device.get("password", ""))
    cmd = [
        "smbclient",
        f"//{host}/{share}",
        *creds,
        "-c",
        "recurse ON; prompt OFF; mdelete *",
    ]
    if sub:
        cmd.extend(["-D", sub])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        out = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode != 0:
            tail = "\n".join(out.splitlines()[-8:])
            return False, tail or f"smbclient exit {proc.returncode}"
        for _ in range(8):
            rmdir = [
                "smbclient",
                f"//{host}/{share}",
                *creds,
                "-c",
                "recurse ON; prompt OFF; rmdir *",
            ]
            if sub:
                rmdir.extend(["-D", sub])
            proc2 = subprocess.run(rmdir, capture_output=True, text=True, timeout=120)
            if proc2.returncode != 0:
                break
        return True, "smbclient cleanup ok"
    except Exception as e:
        return False, str(e)


def endpoint_path_list(ep: dict[str, Any]) -> list[str]:
    """Normalized folder paths for an endpoint (multi- or single-folder)."""
    raw = ep.get("paths")
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            p = str(item or "").strip().strip("/")
            if p not in out:
                out.append(p)
        if out:
            return out
    single = (ep.get("path") or "").strip().strip("/")
    return [single]


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
        paths = endpoint_path_list(ep)
        if len(paths) > 1:
            preview = ", ".join((f"{share}/{p}".strip("/") if p else share) for p in paths[:3])
            if len(paths) > 3:
                preview += ", …"
            return t("endpoint.multi_local", lng, name=name, count=len(paths), paths=preview)
        sub = (ep.get("path") or "").strip().strip("/")
        tail = f"{share}/{sub}".strip("/") if sub else share
        return f"{name}:/{tail}" if tail else f"{name}:"
    vol = normalize_volume_id(ep.get("volume"))
    sub = (ep.get("path") or "").strip().strip("/")
    paths = endpoint_path_list(ep)
    vlabel = volume_label(vol)
    if len(paths) > 1:
        preview = ", ".join(paths[:3])
        if len(paths) > 3:
            preview += ", …"
        return t("endpoint.multi_local", lng, name=name, count=len(paths), paths=preview)
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
        share = validate_smb_share(ep.get("share") or "")
        host = validate_smb_host(str(device.get("host") or ""))
        username = validate_smb_username(str(device.get("username") or ""))
        sub = validate_smb_relpath(ep.get("path") or "")
        mount_point = WORK_MOUNT / str(ep.get("device_id", "x"))
        mount_point.mkdir(parents=True, exist_ok=True)
        cred = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".cred")
        try:
            cred.write(f"username={username}\n")
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
                    f"//{host}/{share}",
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
