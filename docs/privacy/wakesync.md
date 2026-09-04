> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Wake & Sync — Privacy Policy

**App ID:** `com.runlevel.wakesync`  
**Publisher / data controller:** Ivica Kampic, acting as Runlevel  
**E-mail:** runlevel1977@posteo.de  
**Registered / office address:** Ivica Kampic, Runlevel, Leipziger Str. 33, 89537 Giengen, Deutschland  
**Effective date:** 4 September 2026  
**Last updated:** 4 September 2026

This policy describes personal data processed by Wake & Sync when installed on a UGREEN NAS. The app runs locally on the device. Runlevel does not operate a cloud backend for this app and does not receive your NAS data.

## 1. Identity of the controller

- **Controller (software publisher):** Ivica Kampic / Runlevel  
- **E-mail:** runlevel1977@posteo.de  
- **Registered / office address (postal):**  
  Ivica Kampic  
  Runlevel  
  Leipziger Str. 33  
  89537 Giengen  
  Deutschland  

  To exercise your rights, write to **runlevel1977@posteo.de** or to the postal address above.

- **You (the NAS administrator)** decide whether to install the app, which optional credentials to store, and when to uninstall (uninstall removes the app data directory under the package).

## 2. Legal basis

- **EU / GDPR:** processing is necessary to provide the app you requested (Art. 6(1)(b) GDPR — contract) and to protect the NAS (Art. 6(1)(f) — legitimate interest in operating your own device). Optional SMB / notification credentials are stored only after you tap **I agree**. You may tap **Decline** with equal ease; then credential storage stays disabled. You may withdraw consent at any time.
- We do **not sell or share** personal data with third parties.
- There is **no cross-border transfer** by Runlevel. Data stays on your NAS unless you yourself configure Telegram or SMTP (those messages go only to the providers you chose).
- **Sensitive data:** we do not request special-category data. Do not store health, biometric, or similar data in this app.

## 3. Personal information we process (purpose, method, scope)

| Business function | Data | Purpose | Method | Scope / retention |
|---|---|---|---|---|
| Install | UGOS folder shortcut; optional WoL broadcast / source IP | Run the app | UGOS install parameters (no passwords) | Until uninstall |
| Peer NAS / SMB | Display name, IP, MAC, SMB username/password | Wake-on-LAN and sync | Stored **encrypted at rest**; passwords are **RSA-encrypted in transit** on HTTP and are never shown again in the UI | Until you delete the device or uninstall |
| Schedules | Source/target paths, timetable | Run planned sync | Local JSON in the package data dir | Until you delete the plan or uninstall |
| Notifications | Telegram token/chat, SMTP host/user/password, email from/to | Alerts | Entered **in the app** after consent (not as install env); secrets encrypted at rest and on the HTTP path | Until you clear settings or uninstall |
| Consent | Agree/decline, timestamp, policy version | Record your choice | `privacy_consent.json` | Until uninstall |
| App login | App password (you choose) | Block unauthorized access | Salted hash; password is **RSA-encrypted in transit** (not HTTP plaintext) | Until uninstall |
| Logs | Job status (passwords redacted) | Troubleshooting | App log | Until uninstall |

Wake & Sync does **not** collect email addresses except the optional SMTP from/to you enter for alerts. Installation parameters do not include NAS username, SMB password, SMTP password, or Telegram token.

## 4. Children / minors

This app is intended for NAS administrators. It is not directed at children. We do not knowingly collect personal data from children. Do not let minors use administrator credentials. If you believe a child has provided data, uninstall the app and contact us.

## 5. Your rights and how to exercise them

These methods are genuine and effective: the files live on your NAS in the app package data directory, and you can e-mail the controller.

According to the General Data Protection Regulation (GDPR), you have the following rights:

- Accessing, correcting, or deleting your data
- Restricting or opposing data processing
- Receive your data in a portable format
- Withdraw consent at any time
- Complain to data protection regulatory agencies

If you are a resident of California, according to the California Consumer Privacy Act (CCPA), you also have the following rights:

- Understand what personal information we have collected
- Delete your personal information
- Choose not to sell or share your information (we do not sell or share)
- Correct inaccurate information
- Exercise rights without discrimination

If you need to exercise any of the above rights, please contact:  
runlevel1977@posteo.de  
Ivica Kampic, Runlevel, Leipziger Str. 33, 89537 Giengen, Deutschland

Practical local steps on the NAS:

- **Access / portability:** copy the package data folder (JSON settings, consent file). Passwords are stored hashed or encrypted; we cannot recover the plaintext app password.
- **Correction:** change values in the app UI, or delete devices/plans.
- **Deletion:** uninstall the app (this removes the package data directory), or delete individual devices/plans in the UI.
- **Withdraw consent:** tap **Decline** on the privacy dialog, or delete `privacy_consent.json`.
- **Restrict / object:** Decline consent; remove SMB devices; or uninstall.

## 6. Storage period

Local files remain until you delete them or **uninstall** the app. Uninstall removes the package directory, including app password, plans, and encrypted credentials. There is no Runlevel cloud retention.

## 7. Security

- Launch method: **standalone authentication** (`open_type: tab`). On first open a privacy consent dialog (Agree and Decline) is shown. Then you set an app password.
- After login the app issues a **unique 32-character session ID** stored server-side. Request headers such as `user_id` / `user_type` / `Ugreen-User-ID` are **not** accepted as authentication.
- Unauthenticated access shows Sign in / returns 401. Do not expose port 29120 to the public Internet.
- Admin-only (`only_admin: true`).
- Passwords on the LAN HTTP path are protected with **RSA-OAEP (SHA-256)** (UGREEN-accepted alternative where the app listens on HTTP inside the NAS). SMB and notification secrets at rest are encrypted. Adding a device is **rate-limited**. Logs redact secrets.
- Host / share / path values passed to SMB tools are validated separately; the app does not interpolate them into a shell command string.

## 8. Host access

- Bridge networking (not Docker host networking); no privileged mode.
- Only the user-selected UGOS folder (`NAS_DATA_ROOT`) plus the package data directory (not the entire `/home` tree).
- **`docker.sock` is not mounted.**

## Contact

Ivica Kampic / Runlevel  
E-mail: runlevel1977@posteo.de  
Registered / office address:  
Ivica Kampic  
Runlevel  
Leipziger Str. 33  
89537 Giengen  
Deutschland
