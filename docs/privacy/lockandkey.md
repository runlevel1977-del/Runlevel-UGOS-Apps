> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Lock & Key — Privacy Policy

**App ID:** `com.runlevel.lockandkey`  
**Publisher / controller:** Runlevel (Ivica Kampic)  
**Contact:** runlevel1977@posteo.de  
**Effective date:** 25 August 2026  
**Last updated:** 25 August 2026

Local NAS app for vault/key management. Runlevel does not receive your keys.

## 1. Roles and legal basis

Optional credentials only after **I agree**. **Decline** is equally available. No sale/sharing. No cross-border transfer by Runlevel.

## 2. Personal information

| Function | Data | Purpose | Method | Retention |
|---|---|---|---|---|
| Install | Data directory; user-selected folder shortcut | Run the app | UGOS parameters | Until uninstall |
| Vault registry | Vault names, paths, status | Manage vaults | Local JSON | Until deleted |
| Key material | Passphrases / key files you create | Encrypt/decrypt | Stored locally; download APIs require admin gateway auth | Until you delete them |
| Optional UGOS API | Username/password if entered after consent | Volume listing | Encrypted local settings | Until cleared |
| Consent | Agree/decline | Record choice | `privacy_consent.json` | Until deleted |

## 3. Minors

NAS administrators only.

## 4. Rights

Data directory / uninstall / email runlevel1977@posteo.de.

## 5. Security

Standalone authentication (`open_type: tab`): app password required on all APIs including key download; unauthenticated access blocked. Admin-only. Do not expose the app port to the public Internet. `/dev` is not mounted. Only the user-selected folder shortcut plus data directory are mounted. Bridge networking; no host network.

## Contact

runlevel1977@posteo.de (Ivica Kampic, Runlevel)
