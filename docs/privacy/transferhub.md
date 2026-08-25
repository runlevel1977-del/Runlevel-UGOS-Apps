> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Transfer Hub — Privacy Policy

**App ID:** `com.runlevel.transferhub`  
**Publisher / controller:** Runlevel (Ivica Kampic)  
**Contact:** runlevel1977@posteo.de  
**Effective date:** 25 August 2026  
**Last updated:** 25 August 2026

Local NAS app. Runlevel does not receive your files or credentials.

## 1. Roles and legal basis

Administrator-controlled install. Optional SMB credentials stored only after **I agree**. **Decline** is equally available. No sale/sharing. No cross-border transfer by Runlevel.

## 2. Personal information

| Function | Data | Purpose | Method | Retention |
|---|---|---|---|---|
| Install | Data directory, optional folder shortcut | Run copy/sync | UGOS parameters | Until uninstall |
| SMB devices | Host, username, password | File transfer | Local store after consent; passwords are not returned to the UI | Until device deleted |
| Profiles / schedules | Paths, options | Copy/sync jobs | Local JSON | Until deleted |
| Consent | Agree/decline | Record choice | `privacy_consent.json` | Until deleted |
| Logs | Job progress (no passwords) | Troubleshooting | App log | Until deleted |

## 3. Minors

NAS administrators only. Not for children.

## 4. Rights

Edit/delete the data directory or uninstall. Email runlevel1977@posteo.de.

## 5. Security

Standalone authentication (`open_type: tab`): app password required; unauthenticated access blocked. Admin-only. Do not expose the app port to the public Internet. CSRF is mitigated by required authenticated app session on all state-changing APIs. Bridge networking; no host network.

## Contact

runlevel1977@posteo.de (Ivica Kampic, Runlevel)
