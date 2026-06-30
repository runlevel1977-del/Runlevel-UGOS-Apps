# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from crypto_engine import (
    MAGIC,
    MARKER_NAME,
    MANIFEST_NAME,
    build_key_payload,
    count_encrypted_files,
    count_sealable_files,
    decrypt_bytes,
    default_usb_label,
    hash_binding,
    is_wrapped_key_file,
    iter_encrypted,
    key_file_name,
    new_master_key,
    parse_key_payload,
    read_manifest,
    read_marker,
    repair_folder_before_seal,
    repair_folder_before_unlock,
    remove_manifest,
    remove_marker,
    seal_folder,
    serialize_key_file,
    unlock_folder,
    write_marker,
)
from store import (
    append_log,
    delete_vault,
    get_vault,
    is_vault_deleted,
    load_deleted_vault_ids,
    load_vaults,
    mark_vault_deleted,
    new_vault_id,
    set_job,
    upsert_vault,
)
from usb_bind import find_key_on_usb, match_usb_binding, usb_rows_enriched
from usb_stick import owning_vault_for_stick, prepare_usb_stick_for_vault, vault_bound_to_usb_serial
from volumes import host_path_for, normalize_volume_id, resolve_local_path, seal_scan_roots


def _path_has_system_segment(subpath: str) -> bool:
    for part in (subpath or "").strip().strip("/").split("/"):
        if part and "@" in part:
            return True
    return False


def _is_browsable_dir_name(name: str) -> bool:
    n = (name or "").strip()
    return bool(n) and not n.startswith(".") and "@" not in n


def _assert_user_folder_path(subpath: str) -> None:
    from i18n import get_lang, t

    if _path_has_system_segment(subpath):
        raise ValueError(t("err.system_folder", get_lang()))


def public_vault_row(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": v.get("id"),
        "name": v.get("name"),
        "volume": v.get("volume"),
        "path": v.get("path"),
        "host_path": v.get("host_path"),
        "status": v.get("status"),
        "usb_label": v.get("usb_label"),
        "bind_label": bool(v.get("usb_label_hash")),
        "bind_serial": bool(v.get("usb_serial_hash")),
        "file_count": v.get("file_count"),
        "created": v.get("created"),
        "updated": v.get("updated"),
        "key_filename": key_file_name(v.get("id") or ""),
        "key_passphrase": bool(v.get("key_passphrase")),
    }


def list_public_vaults() -> list[dict[str, Any]]:
    try:
        recovered = sync_orphan_vaults()
        if recovered:
            append_log(f"sync_orphan_vaults: {recovered} vault(s) recovered")
    except Exception as exc:
        append_log(f"sync_orphan_vaults failed: {exc}")
    return [public_vault_row(v) for v in load_vaults()]


def _vault_location_key(volume: str, path: str) -> tuple[str, str]:
    return (str(volume or "").strip(), (path or "").strip().strip("/"))


def _known_vault_locations() -> set[tuple[str, str]]:
    return {_vault_location_key(v.get("volume", ""), v.get("path") or "") for v in load_vaults()}


def _apply_key_meta_to_vault(vault: dict[str, Any], meta: dict[str, Any]) -> None:
    if meta.get("name"):
        vault["name"] = meta["name"]
    if meta.get("host_path"):
        vault["host_path"] = meta["host_path"]
    if meta.get("volume"):
        vault["volume"] = meta["volume"]
    if meta.get("path") is not None:
        vault["path"] = meta["path"]
    if meta.get("wrapped"):
        vault["key_passphrase"] = True
    label = (meta.get("usb_label") or "").strip()
    serial = (meta.get("usb_serial") or "").strip()
    model = (meta.get("usb_model") or "").strip()
    if label:
        vault["usb_label"] = label
        vault["usb_label_hash"] = hash_binding(label)
    if serial:
        vault["usb_serial"] = serial
        vault["usb_serial_hash"] = hash_binding(serial)
    elif model:
        vault["usb_model"] = model
        vault["usb_model_hash"] = hash_binding(model)


def _read_key_meta(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if is_wrapped_key_file(data):
        return {
            "vault_id": (data.get("vault_id") or "").strip(),
            "name": (data.get("name") or "").strip(),
            "volume": (data.get("volume") or "").strip(),
            "path": (data.get("path") or "").strip().strip("/"),
            "host_path": (data.get("host_path") or "").strip(),
            "wrapped": True,
        }
    if data.get("magic") != MAGIC:
        return None
    return {
        "vault_id": (data.get("vault_id") or "").strip(),
        "name": (data.get("name") or "").strip(),
        "volume": (data.get("volume") or "").strip(),
        "path": (data.get("path") or "").strip().strip("/"),
        "host_path": (data.get("host_path") or "").strip(),
        "usb_label": (data.get("usb_label") or "").strip(),
        "usb_serial": (data.get("usb_serial") or "").strip(),
        "usb_model": (data.get("usb_model") or "").strip(),
        "wrapped": False,
    }


def _folder_from_key_meta(meta: dict[str, Any]) -> tuple[str, str, Path] | None:
    volume = (meta.get("volume") or "").strip()
    path = (meta.get("path") or "").strip().strip("/")
    if volume in ("1", "2"):
        try:
            folder = resolve_local_path(volume, path)
            if not folder.is_dir():
                return None
            if (
                count_encrypted_files(folder) > 0
                or read_marker(folder)
                or count_sealable_files(folder) > 0
            ):
                return volume, path, folder
        except ValueError:
            pass
    return None


def _folder_vault_state(folder: Path) -> tuple[str, int]:
    state = _resolve_folder_seal_state(folder)
    if state["sealed"]:
        return "locked", int(state["encrypted_count"] or 0)
    open_files = int(state["sealable_count"] or 0)
    return "unlocked", open_files if open_files > 0 else int(state["encrypted_count"] or 0)


def _resolve_folder_seal_state(folder: Path) -> dict[str, Any]:
    marker = read_marker(folder)
    manifest = read_manifest(folder)
    enc = count_encrypted_files(folder)
    sealable = count_sealable_files(folder)
    sealed = enc > 0
    if not sealed and (marker or manifest):
        remove_marker(folder)
        remove_manifest(folder)
        append_log(
            f"removed stale seal metadata at {folder} "
            f"(0 encrypted, {sealable} open files)"
        )
        marker = None
        manifest = None
    sealed_name = ""
    sealed_vault_id = ""
    if sealed:
        sealed_name = ((marker or {}).get("name") or "").strip()
        sealed_vault_id = (
            (marker or {}).get("vault_id")
            or (manifest or {}).get("vault_id")
            or ""
        )
        sealed_vault_id = str(sealed_vault_id).strip()
    return {
        "sealed": sealed,
        "sealed_vault_id": sealed_vault_id,
        "sealed_name": sealed_name,
        "encrypted_count": enc,
        "sealable_count": sealable,
        "marker": marker,
    }


def _vault_root_candidates(
    vol_id: str,
    mount: Path,
    *,
    known_locs: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    known_locs = known_locs if known_locs is not None else _known_vault_locations()
    out: list[dict[str, Any]] = []
    try:
        base = mount.resolve()
    except OSError:
        return out
    seen: set[str] = set()

    def add_folder(folder: Path) -> None:
        key = str(folder.resolve())
        if key in seen:
            return
        try:
            rel = str(folder.resolve().relative_to(base)).replace("\\", "/")
        except ValueError:
            return
        if _vault_location_key(vol_id, rel) in known_locs:
            return
        marker = read_marker(folder)
        manifest = read_manifest(folder)
        file_count = count_encrypted_files(folder)
        if file_count <= 0 and not marker and not manifest:
            return
        vault_id = ""
        name = ""
        if marker:
            vault_id = (marker.get("vault_id") or "").strip()
            name = (marker.get("name") or "").strip()
        if not vault_id and manifest:
            vault_id = (manifest.get("vault_id") or "").strip()
        seen.add(key)
        out.append(
            {
                "volume": vol_id,
                "path": rel,
                "folder": folder,
                "vault_id": vault_id,
                "name": name,
                "file_count": file_count,
            }
        )

    for marker_name in (MARKER_NAME, MANIFEST_NAME):
        try:
            for marker_path in base.rglob(marker_name):
                add_folder(marker_path.parent)
        except OSError:
            continue
    try:
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith(".") or "@" in child.name:
                continue
            if count_encrypted_files(child) > 0 or read_marker(child) or read_manifest(child):
                add_folder(child)
    except OSError:
        pass
    return out


def _folder_by_vault_id_on_disk(vault_id: str) -> tuple[str, str, Path] | None:
    for vol_id, mount in seal_scan_roots():
        try:
            base = mount.resolve()
        except OSError:
            continue
        for marker_name in (MARKER_NAME, MANIFEST_NAME):
            try:
                for marker_path in base.rglob(marker_name):
                    folder = marker_path.parent
                    marker = read_marker(folder)
                    manifest = read_manifest(folder)
                    data = marker or manifest or {}
                    if (data.get("vault_id") or "").strip() != vault_id:
                        continue
                    try:
                        rel = str(folder.resolve().relative_to(base)).replace("\\", "/")
                    except ValueError:
                        continue
                    return vol_id, rel, folder
            except OSError:
                continue
    return None


def _folder_by_trial_decrypt(key_bytes: bytes, vault_id: str) -> tuple[str, str, Path] | None:
    try:
        master_key, _ = parse_key_payload(key_bytes, "")
    except ValueError:
        return None
    matches: list[tuple[str, str, Path]] = []
    known_locs = _known_vault_locations()
    for vol_id, mount in seal_scan_roots():
        for candidate in _vault_root_candidates(vol_id, mount, known_locs=known_locs):
            cand_vid = (candidate.get("vault_id") or "").strip()
            if cand_vid and cand_vid != vault_id:
                continue
            folder = candidate["folder"]
            enc_files = iter_encrypted(folder)
            if not enc_files:
                continue
            try:
                decrypt_bytes(master_key, enc_files[0].read_bytes())
                matches.append((vol_id, candidate["path"], folder))
            except Exception:
                continue
    if len(matches) == 1:
        return matches[0]
    return None


def _locate_folder_for_usb_key(key_path: Path, meta: dict[str, Any]) -> tuple[str, str, Path] | None:
    vault_id = (meta.get("vault_id") or "").strip()
    if not vault_id:
        return None

    located = _folder_from_key_meta(meta)
    if located:
        return located

    located = _folder_by_vault_id_on_disk(vault_id)
    if located:
        return located

    try:
        key_bytes = key_path.read_bytes()
    except OSError:
        return None

    if not meta.get("wrapped"):
        located = _folder_by_trial_decrypt(key_bytes, vault_id)
        if located:
            return located

    unknown: list[tuple[str, str, Path]] = []
    known_locs = _known_vault_locations()
    for vol_id, mount in seal_scan_roots():
        for candidate in _vault_root_candidates(vol_id, mount, known_locs=known_locs):
            if candidate.get("vault_id"):
                continue
            unknown.append((vol_id, candidate["path"], candidate["folder"]))
    if len(unknown) == 1:
        return unknown[0]
    return None


def _iter_usb_key_files() -> list[tuple[dict[str, Any], Path]]:
    found: list[tuple[dict[str, Any], Path]] = []
    for row in usb_rows_enriched():
        mount = Path(row.get("mount") or "")
        if not mount.is_dir():
            continue
        try:
            for child in mount.iterdir():
                if not child.is_file() or child.name.startswith("."):
                    continue
                if not child.name.startswith("lockkey_") or child.suffix.lower() not in {".lk", ".json", ".key"}:
                    continue
                meta = _read_key_meta(child)
                if meta and meta.get("vault_id"):
                    found.append((meta, child))
        except OSError:
            continue
    return found


def _recover_vault_record(
    vault_id: str,
    volume: str,
    path: str,
    folder: Path,
    *,
    name: str = "",
    key_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if is_vault_deleted(vault_id):
        return {}
    status, file_count = _folder_vault_state(folder)
    manifest = read_manifest(folder)
    if status == "locked" and manifest and isinstance(manifest.get("files"), dict):
        file_count = max(file_count, len(manifest["files"]))
    vault: dict[str, Any] = {
        "id": vault_id,
        "name": name or path or "Vault",
        "volume": volume,
        "path": path,
        "host_path": host_path_for(volume, path),
        "container_path": str(folder.resolve()),
        "status": status,
        "usb_label": "",
        "usb_model": "",
        "usb_label_hash": "",
        "usb_serial_hash": "",
        "usb_model_hash": "",
        "key_passphrase": False,
        "file_count": file_count,
        "recovered": True,
        "created": _now(),
        "updated": _now(),
    }
    marker = read_marker(folder)
    if marker and (marker.get("name") or "").strip():
        vault["name"] = (marker.get("name") or "").strip()
    if key_meta:
        _apply_key_meta_to_vault(vault, key_meta)
    upsert_vault(vault)
    append_log(f"recovered vault {vault_id} at {vault['host_path']} ({status})")
    return vault


def sync_orphan_vaults() -> int:
    known_ids = {v.get("id") for v in load_vaults()}
    deleted_ids = load_deleted_vault_ids()
    recovered = 0

    for vol_id, mount in seal_scan_roots():
        try:
            base = mount.resolve()
        except OSError:
            continue
        seen_folders: set[str] = set()
        for marker_name in (MARKER_NAME, MANIFEST_NAME):
            try:
                for marker_path in base.rglob(marker_name):
                    folder = marker_path.parent
                    key = str(folder.resolve())
                    if key in seen_folders:
                        continue
                    seen_folders.add(key)
                    marker = read_marker(folder)
                    manifest = read_manifest(folder)
                    vault_id = ""
                    name = ""
                    if marker:
                        vault_id = (marker.get("vault_id") or "").strip()
                        name = (marker.get("name") or "").strip()
                    if not vault_id and manifest:
                        vault_id = (manifest.get("vault_id") or "").strip()
                    if not vault_id or vault_id in known_ids or vault_id in deleted_ids:
                        continue
                    try:
                        rel = str(folder.resolve().relative_to(base)).replace("\\", "/")
                    except ValueError:
                        continue
                    _recover_vault_record(vault_id, vol_id, rel, folder, name=name)
                    known_ids.add(vault_id)
                    recovered += 1
            except OSError as exc:
                append_log(f"marker scan {mount}: {exc}")
                continue

    for meta, key_path in _iter_usb_key_files():
        vault_id = (meta.get("vault_id") or "").strip()
        if not vault_id or vault_id in known_ids or vault_id in deleted_ids:
            continue
        located = _locate_folder_for_usb_key(key_path, meta)
        if not located:
            append_log(f"usb key {vault_id}: no matching folder found ({key_path.name})")
            continue
        vol, rel, folder = located
        _recover_vault_record(vault_id, vol, rel, folder, name=meta.get("name") or "", key_meta=meta)
        known_ids.add(vault_id)
        recovered += 1

    return recovered


def get_vault_or_recover(vault_id: str) -> dict[str, Any] | None:
    vault = get_vault(vault_id)
    if vault:
        return vault
    sync_orphan_vaults()
    return get_vault(vault_id)


def browse_dirs(volume_id: str, subpath: str) -> dict[str, Any]:
    rel = (subpath or "").strip().strip("/")
    _assert_user_folder_path(rel)
    base = resolve_local_path(volume_id, subpath)
    if not base.is_dir():
        raise ValueError("not a directory")
    dirs: list[dict[str, str]] = []
    try:
        for entry in sorted(base.iterdir(), key=lambda p: p.name.casefold()):
            if not entry.is_dir() or not _is_browsable_dir_name(entry.name):
                continue
            dirs.append({"name": entry.name, "path": str(entry.relative_to(base)).replace("\\", "/")})
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    state = _resolve_folder_seal_state(base)
    return {
        "volume": normalize_volume_id(volume_id),
        "path": rel,
        "host_path": host_path_for(volume_id, rel),
        "container_path": str(base.resolve()),
        "sealable_count": state["sealable_count"],
        "encrypted_count": state["encrypted_count"],
        "sealed": state["sealed"],
        "sealed_vault_id": state["sealed_vault_id"],
        "sealed_name": state["sealed_name"],
        "dirs": dirs,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_usb_row(usb_volume_id: str = "", *, required: bool = True) -> dict[str, Any]:
    from volumes import usb_volume_id as vol_usb_id

    rows = usb_rows_enriched()
    if not rows:
        if required:
            raise ValueError("no USB stick mounted")
        return {}
    if usb_volume_id:
        for row in rows:
            if vol_usb_id(Path(row["mount"])) == usb_volume_id:
                return row
        if required:
            raise ValueError("selected USB stick not mounted")
        return {}
    if len(rows) == 1:
        return rows[0]
    if required:
        raise ValueError("select a USB stick")
    return {}


def _run_job(job_id: str, fn: Callable[[], None]) -> None:
    def worker():
        try:
            set_job(job_id, status="running")
            fn()
            set_job(job_id, status="done")
        except Exception as exc:
            append_log(f"job {job_id} failed: {exc}")
            set_job(job_id, status="error", error=str(exc))

    threading.Thread(target=worker, daemon=True).start()


def create_seal_job(
    name: str,
    volume_id: str,
    subpath: str,
    bind_usb: bool,
    usb_volume_id: str = "",
    key_passphrase: str = "",
) -> tuple[str, dict[str, Any], bytes]:
    _assert_user_folder_path(subpath)
    folder = resolve_local_path(volume_id, subpath)
    if not folder.is_dir():
        raise ValueError("folder not found")
    state = _resolve_folder_seal_state(folder)
    if state["sealed"]:
        sealed_name = (state["sealed_name"] or state["sealed_vault_id"] or "").strip() or "?"
        raise ValueError(f"folder already sealed ({sealed_name}) — unlock first or pick another folder")
    repair_folder_before_seal(folder)
    enc_left = count_encrypted_files(folder)
    open_left = count_sealable_files(folder)
    if enc_left > 0 and open_left > 0:
        raise ValueError(
            "folder is partially sealed (mix of open files and .lkenc) — "
            "unlock with key first or remove orphaned encrypted files manually"
        )
    sealable = int(state["sealable_count"] or 0)
    host = host_path_for(volume_id, subpath)
    if sealable <= 0:
        raise ValueError(
            f"no encryptable files in {host} "
            f"(container: {folder}) — use Volume 1/2 for shared folders, not UGOS shortcut"
        )
    vault_id = new_vault_id()
    key = new_master_key()
    usb_label = default_usb_label(vault_id)
    usb_serial = ""
    usb_label_hash = ""
    usb_serial_hash = ""
    usb_model_hash = ""
    usb_model = ""
    if bind_usb:
        picked = _resolve_usb_row(usb_volume_id, required=True)
        usb_serial = (picked.get("usb_serial") or "").strip()
        other = vault_bound_to_usb_serial(usb_serial)
        if other:
            raise ValueError(
                f"USB-Stick ist bereits Tresor „{other.get('name') or other.get('id')}“ zugeordnet"
            )
        mount = Path(picked["mount"])
        owner = owning_vault_for_stick(mount)
        if owner:
            raise ValueError(
                f"USB-Stick gehört noch zu Tresor „{owner.get('name') or owner.get('id')}“ — "
                f"anderen Stick wählen oder diesen Tresor zuerst löschen"
            )
        usb_label = (picked.get("stick_name") or picked.get("model") or picked.get("volume_label") or usb_label).strip() or usb_label
        usb_model = (picked.get("model") or "").strip()
        usb_label_hash = hash_binding(usb_label)
        if usb_serial:
            usb_serial_hash = hash_binding(usb_serial)
        elif usb_model:
            usb_model_hash = hash_binding(usb_model)
        else:
            usb_model_hash = ""
    rel = (subpath or "").strip().strip("/")
    vault = {
        "id": vault_id,
        "name": (name or rel or "Vault").strip(),
        "volume": volume_id,
        "path": rel,
        "host_path": host,
        "container_path": str(folder.resolve()),
        "status": "locking",
        "usb_label": usb_label,
        "usb_model": usb_model if bind_usb else "",
        "usb_label_hash": usb_label_hash,
        "usb_serial_hash": usb_serial_hash,
        "usb_model_hash": usb_model_hash if bind_usb else "",
        "key_passphrase": bool((key_passphrase or "").strip()),
        "created": _now(),
        "updated": _now(),
    }
    upsert_vault(vault)
    key_payload = build_key_payload(
        vault_id,
        vault["name"],
        key,
        usb_label,
        usb_serial,
        usb_model if bind_usb else "",
        volume=volume_id,
        path=rel,
        host_path=host,
    )
    key_bytes = serialize_key_file(key_payload, key_passphrase)
    job_id = uuid.uuid4().hex[:12]

    def work():
        append_log(f"seal start {vault_id} -> {vault['host_path']} ({folder})")
        try:
            def progress(n: int, rel_name: str) -> None:
                set_job(job_id, progress=n, last=rel_name)

            result = seal_folder(
                folder,
                key,
                vault_id=vault_id,
                vault_name=vault["name"],
                progress_cb=progress,
            )
            count = int(result.get("files") or 0)
            verify = result.get("verify") or {}
            if count <= 0:
                raise ValueError(f"encrypted 0 files in {folder}")
            vault["status"] = "locked"
            vault["updated"] = _now()
            vault["file_count"] = count
            upsert_vault(vault)
            set_job(
                job_id,
                status="done",
                progress=count,
                result={
                    "files": count,
                    "vault_id": vault_id,
                    "host_path": vault["host_path"],
                    "verify": verify,
                },
            )
            append_log(f"seal done {vault_id}: {count} files, verify ok at {vault['host_path']}")
        except Exception as exc:
            append_log(f"seal failed {vault_id}: {exc}")
            try:
                repair_folder_before_seal(folder)
            except Exception as cleanup_exc:
                append_log(f"seal rollback cleanup warning {vault_id}: {cleanup_exc}")
            delete_vault(vault_id)
            remove_marker(folder)
            remove_manifest(folder)
            raise

    set_job(job_id, kind="seal", status="queued", vault_id=vault_id)
    _run_job(job_id, work)
    return job_id, vault, key_bytes


def create_unlock_job(
    vault_id: str,
    key_bytes: bytes | None = None,
    usb_volume_id: str = "",
    key_passphrase: str = "",
) -> str:
    vault = get_vault_or_recover(vault_id)
    if not vault:
        raise ValueError("vault not found")
    if vault.get("status") != "locked":
        raise ValueError("vault not locked")
    folder = resolve_local_path(vault.get("volume", "1"), vault.get("path") or "")
    key: bytes | None = None
    key_data: dict[str, Any] | None = None
    if key_bytes:
        key, key_data = parse_key_payload(key_bytes, key_passphrase)
    else:
        row = _resolve_usb_row(usb_volume_id, required=True)
        ok, reason, _ = match_usb_binding(vault, usb_rows=[row])
        if not ok:
            raise ValueError(reason)
        key_path = find_key_on_usb(vault_id, Path(row["mount"]))
        if not key_path:
            raise ValueError("key file not found on USB")
        key, key_data = parse_key_payload(key_path.read_bytes(), key_passphrase)
    if key_data and (key_data.get("vault_id") or "") != vault_id:
        raise ValueError("key file vault mismatch")
    job_id = uuid.uuid4().hex[:12]

    def work():
        append_log(f"unlock start {vault_id}")
        try:
            def progress(n: int, rel_name: str) -> None:
                set_job(job_id, progress=n, last=rel_name)

            result = unlock_folder(folder, key, progress_cb=progress)
            count = int(result.get("files") or 0)
            verify = result.get("verify") or {}
            vault["status"] = "unlocked"
            vault["updated"] = _now()
            upsert_vault(vault)
            set_job(
                job_id,
                status="done",
                progress=count,
                result={"files": count, "vault_id": vault_id, "verify": verify},
            )
            legacy = verify.get("legacy")
            append_log(f"unlock done {vault_id}: {count} files, verify ok legacy={legacy}")
        except Exception as exc:
            append_log(f"unlock failed {vault_id}: {exc}")
            try:
                repair_folder_before_unlock(folder)
            except Exception as cleanup_exc:
                append_log(f"unlock rollback cleanup warning {vault_id}: {cleanup_exc}")
            raise

    set_job(job_id, kind="unlock", status="queued", vault_id=vault_id)
    _run_job(job_id, work)
    return job_id


def create_relock_job(
    vault_id: str,
    key_bytes: bytes | None = None,
    usb_volume_id: str = "",
    key_passphrase: str = "",
) -> str:
    vault = get_vault_or_recover(vault_id)
    if not vault:
        raise ValueError("vault not found")
    if vault.get("status") != "unlocked":
        raise ValueError("vault not unlocked")
    folder = resolve_local_path(vault.get("volume", "1"), vault.get("path") or "")
    if _resolve_folder_seal_state(folder)["sealed"]:
        raise ValueError("folder already sealed")
    if key_bytes:
        key, key_data = parse_key_payload(key_bytes, key_passphrase)
    else:
        row = _resolve_usb_row(usb_volume_id, required=True)
        ok, reason, _ = match_usb_binding(vault, usb_rows=[row])
        if not ok:
            raise ValueError(reason)
        key_path = find_key_on_usb(vault_id, Path(row["mount"]))
        if not key_path:
            raise ValueError("key file not found on USB")
        key, key_data = parse_key_payload(key_path.read_bytes(), key_passphrase)
    if key_data and (key_data.get("vault_id") or "") != vault_id:
        raise ValueError("key file vault mismatch")
    job_id = uuid.uuid4().hex[:12]

    def work():
        append_log(f"relock start {vault_id}")
        try:
            def progress(n: int, rel_name: str) -> None:
                set_job(job_id, progress=n, last=rel_name)

            result = seal_folder(
                folder,
                key,
                vault_id=vault_id,
                vault_name=vault.get("name") or "Vault",
                progress_cb=progress,
            )
            count = int(result.get("files") or 0)
            verify = result.get("verify") or {}
            vault["status"] = "locked"
            vault["updated"] = _now()
            vault["file_count"] = count
            upsert_vault(vault)
            set_job(
                job_id,
                status="done",
                progress=count,
                result={"files": count, "vault_id": vault_id, "verify": verify},
            )
            append_log(f"relock done {vault_id}: {count} files, verify ok")
        except Exception as exc:
            append_log(f"relock failed {vault_id}: {exc}")
            try:
                repair_folder_before_seal(folder)
            except Exception as cleanup_exc:
                append_log(f"relock rollback cleanup warning {vault_id}: {cleanup_exc}")
            remove_marker(folder)
            remove_manifest(folder)
            raise

    set_job(job_id, kind="relock", status="queued", vault_id=vault_id)
    _run_job(job_id, work)
    return job_id


def write_key_to_usb(usb_volume_id: str, vault_id: str, key_bytes: bytes) -> str:
    row = _resolve_usb_row(usb_volume_id, required=True)
    target_mount = prepare_usb_stick_for_vault(row, vault_id)
    out = target_mount / key_file_name(vault_id)
    out.write_bytes(key_bytes)
    vault = get_vault(vault_id)
    if vault:
        serial = (row.get("usb_serial") or "").strip()
        vault["usb_serial"] = serial
        vault["usb_volume_id"] = usb_volume_id
        vault["updated"] = _now()
        upsert_vault(vault)
    append_log(f"key written to {out} (stick prepared, single key only)")
    return str(out)


def remove_vault_record(vault_id: str, force: bool = False) -> bool:
    vault = get_vault(vault_id)
    if not vault:
        return False
    status = (vault.get("status") or "").strip()
    if status == "locking":
        raise ValueError("vault is busy")
    if status == "locked" and not force:
        raise ValueError("vault is locked — confirm delete to remove from list only")
    append_log(f"vault record removed {vault_id} ({vault.get('name')}) force={force}")
    try:
        folder = resolve_local_path(vault.get("volume", "1"), vault.get("path") or "")
        _resolve_folder_seal_state(folder)
    except ValueError:
        pass
    mark_vault_deleted(vault_id)
    return delete_vault(vault_id)
