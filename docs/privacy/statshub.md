> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Stats Hub — Privacy Policy

**App ID:** `com.runlevel.statshub`  
**Publisher / controller:** Runlevel (Ivica Kampic)  
**Contact:** runlevel1977@posteo.de  
**Effective date:** 25 August 2026  
**Last updated:** 25 August 2026

This policy describes personal data processed by Stats Hub when installed on a UGREEN NAS. The app runs locally on the device. Runlevel does not operate a cloud backend for this app and does not receive your NAS data.

## 1. Roles and legal basis

- **Controller:** You (the NAS administrator) decide whether to install the app and which optional credentials to store. Runlevel provides the software.
- **Legal basis (EU):** processing is necessary to provide the app you requested (contract / legitimate interest in operating your own NAS). Optional credentials are stored only after you tap **I agree** in the in-app consent dialog. You may tap **Decline** with equal ease; then credential storage stays disabled.
- We do **not sell or share** personal data with third parties. There is **no cross-border transfer** by Runlevel. Data stays on your NAS unless you yourself configure an outbound notification in another Runlevel app.

## 2. Personal information we process (purpose, method, scope)

| Business function | Data | Purpose | Method | Scope / retention |
|---|---|---|---|---|
| Install | Data directory path you choose | Store local settings/log | Written by UGOS to the container mount | Until you delete the folder or uninstall |
| Live dashboard | CPU/RAM/disk/network metrics, hostname | Show NAS status | Read from the NAS (`/proc`, `/sys`) | In-memory only; not sent off-device |
| Optional UGOS API | NAS username and password (if you enter them in the app after consent) | Richer live metrics via the local UGOS API | Stored **encrypted** in `settings.json` on the data directory; not passed as container environment variables | Until you clear settings or delete the data directory |
| Privacy consent | Agree/decline, timestamp | Record your choice | `privacy_consent.json` | Until you delete the data directory |
| App login | App password (you choose) | Block unauthorized access | Salted hash in `app_auth.json` on the data directory | Until you delete the data directory |
| Application log | Errors, collection issues (no passwords) | Troubleshooting | `stats-hub.log` | Until you delete the file |

Stats Hub does **not** collect email addresses. Optional UGOS credentials are entered **inside the app**, not during App Center install.

## 3. Children / minors

This app is intended for NAS administrators. It is not directed at children. Do not let minors use administrator credentials. We do not knowingly collect data from children.

## 4. Your rights and how to exercise them

You may access, correct, or delete local app data by editing or deleting the **Data directory** on the NAS, or by uninstalling the app. To withdraw consent, tap **Decline** on the next consent prompt after deleting `privacy_consent.json`, or delete that file. For questions, email **runlevel1977@posteo.de**. These methods are real: the files are under your control on the NAS.

## 5. Security

- Launch method: **standalone authentication** (`open_type: tab`). On first open you set an app password (stored hashed on the NAS only). Every page/API except health/login requires that session.
- Unauthenticated access shows Sign in / returns 401. Do not expose port 29125 to the public Internet.
- Admin-only (`only_admin: true`).
- Optional UGOS API passwords at rest are encrypted. The app login password is a salted hash only.
- Opened from the UGOS App Center after you have logged into the NAS; the app still requires its own password.

## 6. Host access

- Bridge networking (not Docker host networking); no privileged mode.
- `/sys` read-only for metrics; optional volume paths for folder-size scans.
- `/dev` mounted **read-only** only so `smartctl` can read disk temperatures.
- `docker.sock` mounted **read-only** only so the dashboard can list local Docker containers.

## Contact

runlevel1977@posteo.de (Ivica Kampic, Runlevel)
