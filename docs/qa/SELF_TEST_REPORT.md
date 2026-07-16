# Runlevel UGOS Apps — Self-Test Case Report

**For:** UGREEN App Center QA  
**Developer / Publisher:** Runlevel (Ivica Kampic)  
**Report date:** 2026-07-16  
**Tester:** Ivica Kampic (Runlevel)  
**Contact:** runlevel1977@posteo.de  

## Test environment

| Item | Value |
| --- | --- |
| Device model | UGREEN DXP4800 |
| Architecture | amd64 |
| UGOS Pro version | 1.17.0.0095 |
| Docker suite version | 1.17.0.0059 (`com.ugreen.docker`) |
| Docker Engine | 29.4.3 |
| LAN | Private home/lab network |
| Browser / client | UGOS desktop App Center + in-app browser tab |
| Runtime check (2026-07-16) | All six Runlevel containers Up |

## Packages under test

| App | App ID | Version (project.yaml) | Result |
| --- | --- | --- | --- |
| Stats Hub | `com.runlevel.statshub` | 0.2.32.0004 | Pass |
| Transfer Hub | `com.runlevel.transferhub` | 0.6.26.0003 | Pass |
| Backup Verifier | `com.runlevel.backupverifier` | 0.3.14.0004 | Pass |
| Wake & Sync | `com.runlevel.wakesync` | 0.1.31.0003 | Pass |
| Security Hub | `com.runlevel.securityhub` | 0.1.12.0004 | Pass |
| Lock & Key | `com.runlevel.lockandkey` | 0.1.25.0004 | Pass |

> After metadata-only UPK rebuilds for review resubmission, update the build suffix (`.xxxx`) here; `x.y.z` may stay the same if only compliance links changed.

## Cross-cutting checks

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| C1 | Install with Docker dependency present | Pass | All six |
| C2 | Admin-only access | Pass | Non-admin not required for listing |
| C3 | App opens (`open_type: tab`) | Pass | |
| C4 | Data directory writable | Pass | Per-app `DATA_PATH` |
| C5 | App Center: official / publisher links → Runlevel GitHub | Pass | Not ugnas.com |
| C6 | App Center: technical_support_link → mailto + Issues | Pass | |
| C7 | App Center: help → per-app guide | Pass | `docs/help/<slug>.md` |
| C8 | In-app footer Help / Support / Privacy | Pass | |
| C9 | Locales en-US / de-DE / zh-CN metadata present | Pass | |
| C10 | Language switch in UI (en/de/zh where available) | Pass | |

## Per-app functional cases

### Stats Hub

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| SH1 | Dashboard loads | Pass | |
| SH2 | Live metrics refresh | Pass | CPU/RAM/network or volumes |
| SH3 | Optional UGOS API credentials | Pass | When configured |

### Transfer Hub

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| TH1 | Privacy consent for credentials | Pass | |
| TH2 | Local → local transfer | Pass | Small test folder |
| TH3 | Job progress visible | Pass | |
| TH4 | Stop job | Pass | |
| TH5 | SMB transfer (LAN) | Pass | Lab SMB target |

### Backup Verifier

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| BV1 | Identical trees → match | Pass | |
| BV2 | Modified file → mismatch | Pass | |
| BV3 | Read-only behavior (no write to compared paths) | Pass | |

### Wake & Sync

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| WS1 | Add target device (IP/MAC/SMB) | Pass | |
| WS2 | Create plan + run sync (target online) | Pass | Incremental rclone |
| WS3 | Multi-folder sources | Pass | |
| WS4 | Job progress + stop | Pass | |
| WS5 | WoL when target offline | Pass | Lab: second NAS/PC with WoL |
| WS6 | WoL source IP = UGREEN IP; broadcast = subnet | Pass | Documented in help |

### Security Hub

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| SE1 | Overview / events load | Pass | Host log read-only |
| SE2 | No firewall mutation from UI | Pass | |

### Lock & Key

| ID | Case | Result | Notes |
| --- | --- | --- | --- |
| LK1 | Seal disposable test folder | Pass | |
| LK2 | Download key file | Pass | Key not left as recoverable NAS secret |
| LK3 | Unlock with key | Pass | |

## Known limitations / notes for QA

1. All apps require **Docker** suite and **admin** user.
2. Wake & Sync WoL needs a target that supports magic packet; otherwise test sync with target already awake.
3. Lock & Key: use **disposable** data only — lost keys cannot be recovered by the publisher.
4. SMB credentials are stored locally on the NAS data path (user-controlled); privacy consent applies where required.
5. Architecture submitted: **amd64** (as packaged).

## Overall verdict

**Ready for UGREEN QA core-workflow testing** with the materials in `docs/qa/CORE_WORKFLOWS.md` and per-app help under `docs/help/`.

**Signed:** Ivica Kampic / Runlevel — 2026-07-16
