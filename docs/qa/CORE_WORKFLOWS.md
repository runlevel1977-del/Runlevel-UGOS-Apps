# Runlevel UGOS Apps — Core Application Workflows

**For:** UGREEN App Center QA  
**Developer / Publisher:** Runlevel (Ivica Kampic)  
**Date:** 2026-07-16  
**Repository:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps  

This document describes how to install, configure, and exercise the **core workflow** of each submitted application.

## Common prerequisites (all six apps)

1. UGREEN NAS with **UGOS Pro** ≥ `1.13.0.0000` (amd64).
2. **Docker** suite (`com.ugreen.docker`) ≥ `1.7.0.0000` installed.
3. Administrator login (all apps are `only_admin: true`).
4. Create a dedicated data folder per app under e.g. `/volume1/docker/<app>/data`.

## Localization / launch regions

| Locale | Markets |
| --- | --- |
| `en-US` | Fallback / English markets |
| `de-DE` | Germany, Austria, Switzerland |
| `zh-CN` | China |

Store metadata (name, description, author, official, help, publisher) is localized in each UPK `project.yaml`. In-app UI supports the same languages.

## Developer / publisher identity (App Center links)

| Field | Value |
| --- | --- |
| Author / Publisher | Runlevel |
| Official | https://github.com/runlevel1977-del/Runlevel-UGOS-Apps |
| Publisher link | https://github.com/runlevel1977-del |
| Help | Per-app guide under `docs/help/<slug>.md` |
| Technical support | `mailto:runlevel1977@posteo.de` · https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues |

---

## 1. Stats Hub (`com.runlevel.statshub`)

**Goal:** Live system statistics dashboard opens and refreshes.

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Install app; set Data directory | Install succeeds; container runs |
| 2 | Open Stats Hub | UI loads on port 29125 |
| 3 | Wait for refresh | CPU/RAM/network (or volume) widgets show values |
| 4 | Optional: set UGOS API user/password in settings | Metrics still update / richer data |
| 5 | Open Help / Support footer links | Reach GitHub help + mailto support |

**User guide:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/statshub.md

---

## 2. Transfer Hub (`com.runlevel.transferhub`)

**Goal:** Transfer files from a local folder to another local or SMB destination.

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Install; set Data directory | App opens |
| 2 | Accept privacy consent (credential storage) | Consent saved |
| 3 | Add source (local volume path) and destination | Devices/profiles save |
| 4 | Create profile and Start job | Progress shown; files appear at destination |
| 5 | Stop job mid-run (optional) | Job stops cleanly |

**User guide:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/transferhub.md

**Minimal test data:** small folder with a few text files.

---

## 3. Backup Verifier (`com.runlevel.backupverifier`)

**Goal:** Detect match / mismatch between two folder trees (read-only).

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Install; set Data directory | App opens |
| 2 | Prepare folder A and identical copy B | Ready |
| 3 | Create job A vs B; Run | Report: match (no critical mismatches) |
| 4 | Change one file in B; Run again | Mismatch reported |
| 5 | Optional: Telegram/SMTP alert | Notification received if configured |

**User guide:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/backupverifier.md

---

## 4. Wake & Sync (`com.runlevel.wakesync`)

**Goal:** WoL target (if offline) → wait for SMB → incremental sync.

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Install; set Data directory; optional WoL broadcast / source IP | App opens |
| 2 | Enable WoL on target NAS/PC; note MAC + IP | Target ready |
| 3 | Add target device + SMB credentials | Device saved |
| 4 | Create plan: source folder(s) → destination | Plan saved |
| 5 | Run once (target awake or asleep) | WoL if needed; sync completes; progress visible |
| 6 | Change one source file; run again | Incremental transfer only |

**WoL parameters:**

- **WoL source IP** = UGREEN NAS IP on the send path (not target IP).
- **WoL broadcast** = subnet broadcast (e.g. `192.168.2.255`), not target IP.

**User guide:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/wakesync.md

**If no second NAS in the lab:** use a LAN PC with SMB + WoL, or verify UI + dry configuration and mark WoL hardware step as N/A with note.

---

## 5. Security Hub (`com.runlevel.securityhub`)

**Goal:** Admin can view recent authentication / login-related events.

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Install; set Data directory | App opens |
| 2 | Open Security Hub | Event list or overview loads |
| 3 | Trigger / filter if available | No crash; data from host logs |
| 4 | Confirm read-only (no firewall change controls that write) | No system mutation from UI |

**User guide:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/securityhub.md

---

## 6. Lock & Key (`com.runlevel.lockandkey`)

**Goal:** Seal a test folder and unlock it again with the key file.

| Step | Action | Expected |
| --- | --- | --- |
| 1 | Install; set Data directory | App opens |
| 2 | Create small test folder with sample files on Volume 1 | Ready |
| 3 | Seal vault; download key file | Folder sealed; key obtained |
| 4 | Unlock with key file | Files restored / readable |
| 5 | Confirm key is not stored in app data as recoverable secret | Keys remain with user |

**User guide:** https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/lockandkey.md

**Warning for QA:** use only disposable test data.

---

## In-app help

Each app footer includes **Help**, **Privacy**, **Support (email)**, and **Issues** links pointing to the Runlevel GitHub repository (not ugnas.com).

## Contact

Ivica Kampic — Runlevel — runlevel1977@posteo.de
