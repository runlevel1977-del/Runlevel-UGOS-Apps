> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Security Hub — Privacy Policy

**App ID:** `com.runlevel.securityhub`  
**Publisher / data controller:** Ivica Kampic, acting as Runlevel  
**E-mail:** runlevel1977@posteo.de  
**Registered / office address:** Ivica Kampic, Runlevel, Leipziger Str. 33, 89537 Giengen, Deutschland  
**Effective date:** 4 September 2026  
**Last updated:** 4 September 2026

This policy describes personal data processed by Security Hub when installed on a UGREEN NAS. The app runs locally on the device. Runlevel does not operate a cloud backend for this app and does not receive your NAS data.

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

- **You (the NAS administrator)** decide whether to install the app, which optional credentials to store, and when to delete the data directory.

## 2. Legal basis

- **EU / GDPR:** processing is necessary to provide the app you requested (Art. 6(1)(b) GDPR — contract) and to protect the NAS (Art. 6(1)(f) — legitimate interest in operating your own device). Optional UGOS credentials are stored only after you tap **I agree**. You may tap **Decline** with equal ease; then credential storage stays disabled. You may withdraw consent at any time.
- We do **not sell or share** personal data with third parties.
- There is **no cross-border transfer** by Runlevel. Data stays on your NAS. Runlevel does not operate servers that receive your NAS content.
- **Sensitive data:** we do not request special-category data. Do not store health, biometric, or similar data in this app.

## 3. Personal information we process (purpose, method, scope)

| Business function | Data | Purpose | Method | Scope / retention |
|---|---|---|---|---|
| Install | Data directory path you choose | Store local settings/log | Written by UGOS to the container mount | Until you delete the folder or uninstall |
| Log view | Usernames, IP addresses, login times already present in NAS logs | Security review | Read-only mount of host log paths | Displayed in the UI; not copied off-device by Runlevel |
| Optional UGOS API | NAS username and password (only if you enter them in the app after consent) | Extra status | Stored encrypted locally; not required at install | Until you clear settings or delete the data directory |
| Privacy consent | Agree/decline, timestamp, policy version | Record your choice | `privacy_consent.json` | Until you delete the data directory |
| App login | App password (you choose) | Block unauthorized access | Salted hash; the password is **RSA-OAEP-encrypted in transit** (not sent as HTTP plaintext) | Until you delete the data directory |
| Application log | App errors (no passwords) | Troubleshooting | App log file | Until you delete the file |

Security Hub does **not** collect email addresses. Installation parameters do not include NAS username or password.

## 4. Children / minors

This app is intended for NAS administrators. It is not directed at children. We do not knowingly collect personal data from children. Do not let minors use administrator credentials. If you believe a child has provided data, delete the data directory and contact us.

## 5. Your rights and how to exercise them

These methods are genuine and effective: the files live on your NAS under the data directory you chose, and you can e-mail the controller.

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

- **Access / portability:** copy the data directory (JSON settings, consent file). Passwords are stored hashed or encrypted; we cannot recover the plaintext app password.
- **Correction:** change values in the app UI, or edit/delete files in the data directory.
- **Deletion:** delete the data directory, or uninstall the app and remove that folder.
- **Withdraw consent:** tap **Decline** on the privacy dialog, or delete `privacy_consent.json`.
- **Restrict / object:** Decline consent; or uninstall.

## 6. Storage period

Local files remain until you delete them or remove the data directory. There is no Runlevel cloud retention, because Runlevel does not receive the data.

## 7. Security

- Launch method: **standalone authentication** (`open_type: tab`). On first open a privacy consent dialog (Agree and Decline) is shown. Then you set an app password.
- After login the app issues a **unique 32-character session ID** stored server-side. Request headers such as `user_id` / `user_type` / `Ugreen-User-ID` are **not** accepted as authentication.
- Unauthenticated access shows Sign in / returns 401. Do not expose port 29130 to the public Internet.
- Admin-only (`only_admin: true`).
- Passwords on the LAN HTTP path are protected with **RSA-OAEP (SHA-256)** (UGREEN-accepted alternative where the app listens on HTTP inside the NAS). The app login password is stored as a salted hash only.

## 8. Host access

- Bridge networking (not Docker host networking); no privileged mode.
- Host logs mounted **read-only** (`/var/log`, UGOS log path) so the dashboard can show login events.
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
