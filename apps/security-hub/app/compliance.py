# -*- coding: utf-8 -*-
"""In-app compliance links and optional privacy consent (credential storage)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = os.environ.get("RUNLEVEL_APPS_REPO", "https://github.com/runlevel1977-del/Runlevel-UGOS-Apps")
PRIVACY_SLUG = os.environ.get("RUNLEVEL_PRIVACY_SLUG", "statshub")
NEEDS_CREDENTIAL_CONSENT = os.environ.get("RUNLEVEL_CREDENTIAL_CONSENT", "0") == "1"
SUPPORT_EMAIL = "runlevel1977@posteo.de"


def public_links() -> dict[str, str]:
    base = REPO.rstrip("/")
    return {
        "privacy": f"{base}/blob/main/docs/privacy/{PRIVACY_SLUG}.md",
        "eula": f"{base}/blob/main/docs/EULA.md",
        "license": f"{base}/blob/main/LICENSE",
        "third_party": f"{base}/blob/main/THIRD_PARTY_LICENSES.md",
        "source": base,
        "help": f"{base}/blob/main/docs/help/README.md",
        "support_email": f"mailto:{SUPPORT_EMAIL}",
        "issues": f"{base}/issues",
        "companion": "https://github.com/runlevel1977-del/UgreenNASAdmin",
    }


def consent_path(data_dir: Path) -> Path:
    return data_dir / "privacy_consent.json"


def load_consent(data_dir: Path) -> dict[str, Any] | None:
    path = consent_path(data_dir)
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def has_privacy_consent(data_dir: Path) -> bool:
    if not NEEDS_CREDENTIAL_CONSENT:
        return True
    row = load_consent(data_dir)
    return bool(row and row.get("accepted"))


def save_privacy_consent(data_dir: Path) -> dict[str, Any]:
    data_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "accepted": True,
        "accepted_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "privacy_url": public_links()["privacy"],
    }
    with consent_path(data_dir).open("w", encoding="utf-8") as fh:
        json.dump(row, fh, indent=2, ensure_ascii=False)
    return row


def consent_required_response() -> tuple[dict[str, Any], int]:
    return (
        {
            "ok": False,
            "error": "privacy_consent_required",
            "privacy_url": public_links()["privacy"],
        },
        403,
    )


def compliance_context(data_dir: Path) -> dict[str, Any]:
    links = public_links()
    return {
        "compliance_links": links,
        "privacy_consent_required": NEEDS_CREDENTIAL_CONSENT,
        "privacy_consent_given": has_privacy_consent(data_dir),
    }
