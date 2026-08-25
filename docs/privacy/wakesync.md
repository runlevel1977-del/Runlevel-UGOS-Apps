> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Wake & Sync — Privacy Policy

**App ID:** `com.runlevel.wakesync`  
**Publisher / controller:** Runlevel (Ivica Kampic)  
**Contact:** runlevel1977@posteo.de  
**Effective date:** 25 August 2026  
**Last updated:** 25 August 2026

The app runs locally on your UGREEN NAS. Runlevel does not operate a cloud backend for this app.

## 1. Roles and legal basis

You (the NAS administrator) control installation and optional credentials. Legal basis (EU): providing the app you requested; optional credentials only after **I agree**. **Decline** is offered with equal ease. We do **not sell or share** personal data. Runlevel performs **no cross-border transfer**. Data stays on your NAS except optional Telegram/SMTP that you configure (those go to the providers you chose).

## 2. Personal information (purpose, method, scope)

| Function | Data | Purpose | Method | Retention |
|---|---|---|---|---|
| Install | Data directory; optional UGOS folder path; optional WoL broadcast/source IP | Run the app | UGOS install parameters | Until uninstall / folder delete |
| Peer NAS / SMB | Display name, IP, MAC, SMB username/password | Wake-on-LAN and sync | Stored locally after consent; passwords must not be shown again in the UI | Until you delete the device |
| Schedules | Source/target paths, timetable | Run planned sync | Local JSON | Until you delete the plan |
| Notifications | Telegram token/chat, SMTP host/user/password, email from/to | Alerts | Local settings after consent; optional install fields if you fill them | Until you clear settings |
| Consent | Agree/decline + timestamp | Record choice | `privacy_consent.json` | Until deleted |
| Logs | Job status (passwords redacted) | Troubleshooting | App log | Until deleted |

## 3. Minors

For NAS administrators only. Not directed at children. We do not knowingly collect children's data.

## 4. Rights

Access/correct/delete by editing the data directory or uninstalling. Withdraw consent by declining in-app or deleting `privacy_consent.json`. Email runlevel1977@posteo.de.

## 5. Security

Standalone authentication (`open_type: tab`): app password required after first launch; unauthenticated access blocked. Admin-only. Do not expose the app port to the public Internet. MAC addresses are format-validated. Volumes: only the user-selected UGOS folder plus the data directory (not the entire `/home` tree). Bridge networking; no host network.

## Contact

runlevel1977@posteo.de (Ivica Kampic, Runlevel)
