> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Lock & Key — Privacy Policy

**App ID:** `com.runlevel.lockandkey`  
**Publisher / data controller:** Ivica Kampic, acting as Runlevel  
**E-mail:** runlevel1977@posteo.de  
**Registered / office address:** Ivica Kampic, Runlevel, Leipziger Str. 33, 89537 Giengen, Deutschland  
**Effective date:** 4 September 2026  
**Last updated:** 4 September 2026

This policy describes personal data processed by Lock & Key when installed on a UGREEN NAS. The app runs locally on the device. Runlevel does not operate a cloud backend for this app and does not receive your keys or vault contents.

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

- **You (the NAS administrator)** decide whether to install the app, which folders to seal, and when to uninstall.

## 2. Legal basis

- **EU / GDPR:** processing is necessary to provide the app you requested (Art. 6(1)(b) GDPR — contract) and to protect the NAS (Art. 6(1)(f) — legitimate interest in operating your own device). Optional key-file passwords are used only after you tap **I agree**. You may tap **Decline** with equal ease. You may withdraw consent at any time.
- We do **not sell or share** personal data with third parties.
- There is **no cross-border transfer** by Runlevel. Data stays on your NAS (and on USB if you copy a key file yourself).
- **Sensitive data:** we do not request special-category data. Do not store health, biometric, or similar data in this app.

## 3. Personal information we process (purpose, method, scope)

| Business function | Data | Purpose | Method | Scope / retention |
|---|---|---|---|---|
| Install | Data directory; UGOS folder shortcut | Run the app | UGOS install parameters (no passwords) | Until uninstall |
| Vault registry | Vault names, paths, status | Manage sealed folders | Local JSON in the data directory | Until you delete the vault or uninstall |
| Key material | Encryption key file; optional key-file password | Seal / unlock folders | Key is **not** kept on the NAS after you download it or write it to USB. Passwords and key files on the HTTP path are **RSA-encrypted in transit** | Until you delete the key / uninstall |
| Consent | Agree/decline, timestamp, policy version | Record your choice | `privacy_consent.json` | Until uninstall |
| App login | App password (you choose) | Block unauthorized access | Salted hash; password is **RSA-encrypted in transit** (not HTTP plaintext) | Until uninstall |
| Logs | Job status (secrets redacted) | Troubleshooting | App log | Until uninstall |

Installation parameters do not include NAS username or NAS password. Losing the key file means sealed content cannot be recovered.

## 4. Children / minors

This app is intended for NAS administrators. It is not directed at children. We do not knowingly collect personal data from children. Do not let minors use administrator credentials. If you believe a child has provided data, uninstall the app and contact us.

## 5. Your rights and how to exercise them

These methods are genuine and effective: the files live on your NAS in the app data directory, and you can e-mail the controller.

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

- **Access / portability:** copy the data directory (JSON settings, consent file). The app password is hashed; we cannot recover the plaintext. Vault encryption keys are in the `.lk` file you downloaded — not in the data directory after download.
- **Correction:** change values in the app UI, or delete vault records.
- **Deletion:** uninstall the app or delete individual vaults in the UI. Delete key files you stored yourself (download / USB).
- **Withdraw consent:** tap **Decline** on the privacy dialog, or delete `privacy_consent.json`.
- **Restrict / object:** Decline consent or uninstall.

## 6. Storage period

Local files remain until you delete them or **uninstall** the app. There is no Runlevel cloud retention.

## 7. Security

- Launch method: **standalone authentication** (`open_type: tab`). On first open a privacy consent dialog (Agree and Decline) is shown. Then you set an app password.
- After login the app issues a **unique 32-character session ID** stored server-side. Request headers such as `user_id` / `user_type` / `Ugreen-User-ID` are **not** accepted as authentication.
- Unauthenticated access shows Sign in / returns 401. Do not expose port 29135 to the public Internet.
- Admin-only (`only_admin: true`).
- Passwords and key files on the LAN HTTP path are protected with **RSA-OAEP (SHA-256)** (UGREEN-accepted alternative where the app listens on HTTP inside the NAS).

## 8. Host access

- Bridge networking (not Docker host networking); no privileged mode.
- User-selected UGOS folder, USB mount for key files, plus the data directory. `/dev` is not mounted. **`docker.sock` is not mounted.**

## Contact

Ivica Kampic / Runlevel  
E-mail: runlevel1977@posteo.de  
Registered / office address:  
Ivica Kampic  
Runlevel  
Leipziger Str. 33  
89537 Giengen  
Deutschland
