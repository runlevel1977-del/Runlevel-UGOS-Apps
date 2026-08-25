> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Backup Verifier — Privacy Policy

**App ID:** `com.runlevel.backupverifier`  
**Publisher / controller:** Runlevel (Ivica Kampic)  
**Contact:** runlevel1977@posteo.de  
**Effective date:** 25 August 2026  
**Last updated:** 25 August 2026

Local NAS app. Compare is read-only. Runlevel does not receive your files.

## 1. Roles and legal basis

Optional SMB credentials only after **I agree**. **Decline** is equally available. No sale/sharing. No cross-border transfer by Runlevel.

## 2. Personal information

| Function | Data | Purpose | Method | Retention |
|---|---|---|---|---|
| Install | Data directory, optional folder shortcut | Run verifier | UGOS parameters | Until uninstall |
| SMB devices | Host, username, password | Compare over SMB | Local store after consent; **passwords are never returned to the frontend** | Until device deleted |
| Jobs / schedules | Paths, options | Verification | Local JSON | Until deleted |
| Notifications | Telegram/SMTP/email if enabled | Alerts | Local after consent | Until cleared |
| Consent | Agree/decline | Record choice | `privacy_consent.json` | Until deleted |

## 3. Minors

NAS administrators only.

## 4. Rights

Data directory / uninstall / email runlevel1977@posteo.de.

## 5. Security

Standalone authentication (`open_type: tab`): app password required; unauthenticated access blocked. Admin-only. Do not expose the app port to the public Internet. Browse paths are confined to configured mounts. Bridge networking; no host network.

## Contact

runlevel1977@posteo.de (Ivica Kampic, Runlevel)
