> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Moving Files — Privacy Policy

**App ID:** `com.runlevel.movingfiles`  
**Publisher / data controller:** Ivica Kampic, acting as Runlevel  
**E-mail:** runlevel1977@posteo.de  
**Registered / office address:** Ivica Kampic, Runlevel, Leipziger Str. 33, 89537 Giengen, Deutschland  
**Effective date:** 3 November 2026  
**Last updated:** 3 November 2026

This policy describes personal data processed by Moving Files when installed on a UGREEN NAS. The app runs locally on the device. Runlevel does not operate a cloud backend for this app and does not receive your files.

中文摘要：生效日期和更新日期均为 2026年11月3日。控制者是 Ivica Kampic / Runlevel（runlevel1977@posteo.de，Leipziger Str. 33, 89537 Giengen，德国）。法律依据是 GDPR 第6条第1款(b)和(f)。我们不出售、不共享个人信息，Runlevel 不做跨境传输。本应用不面向未成年人。IP 或主机名、SMB 用户名、密码和 MAC 仅用于访问您选择的 SMB 共享并发送网络唤醒；浏览器在 HTTP 上用 RSA-OAEP 加密后发送，只保存在本 NAS 的 state.json，直到您删除设备或卸载。本机局域网地址只在内存中用于选择唤醒网卡，不保存、不上传。归档密码同样经 RSA-OAEP 传输，GET `/api/state` 不返回明文密码。您可访问、更正、删除、限制、反对、导出数据、撤回同意，并向监管机构投诉；请发邮件至 runlevel1977@posteo.de，或在 NAS 上删除设备/任务，或卸载应用。

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

- **You (the NAS administrator)** decide whether to install the app, which folders to grant, and when to uninstall (uninstall removes the app data directory).

## 2. Legal basis

- **EU / GDPR:** processing is necessary to provide the app you requested (Art. 6(1)(b) GDPR — contract) and to operate your own NAS (Art. 6(1)(f) — legitimate interest).
- We do **not sell or share** personal data with third parties.
- There is **no cross-border transfer** by Runlevel. Data stays on your NAS unless you copy files to an SMB host you chose.
- **Sensitive data:** we do not request special-category data. Do not store health, biometric, or similar data in this app.

## 3. Personal information we process (purpose, method, scope)

| Business function | Data | Purpose | Method | Scope / retention |
|---|---|---|---|---|
| Install | Granted NAS folder paths (Volume 1 required; Volume 2 optional) | Read/write only folders you authorize | UGOS install parameters (`allow_add_access_path`); no passwords | Until you change them or uninstall |
| Connections | IP address or hostname, SMB username, password, MAC address | Reach the SMB share you chose and send Wake-on-LAN | You type them in Connections. The browser encrypts them with RSA-OAEP (SHA-256) before HTTP. Stored only in local `state.json` | Until you delete the device or uninstall |
| Wake-on-LAN | Destination MAC and host IP; this NAS LAN address read from the local network interface | Send the magic packet on the correct LAN interface | UDP on your LAN only. The NAS address is used in memory and is not stored or sent to Runlevel | MAC/host until you delete the device; NAS address is not retained |
| SMB devices | Display name and share name | Show the device in the job list | Stored in local `state.json` on the NAS | Until you delete the device or uninstall |
| Jobs / schedules | Source and destination paths, mode, times | Run copy/move on demand or on a schedule | Local `state.json` | Until you delete the job or uninstall |
| Backup | Source/destination, keep count, optional **archive password** | Create `.tar.gz` / `.tar.gz.enc` archives and restore them | Archive password stored in `state.json`; omitted from GET `/api/state` (flag `hasPassword` only) | Until you clear it or uninstall |
| Restore | Archive names, destination path, password you type | Decrypt and extract an archive | Password used in memory for that restore; not stored from the restore form | Not retained after the job |
| Wake-on-LAN | MAC address, LAN broadcast | Wake an offline SMB host before a job | UDP magic packet on your LAN only | MAC stored with the device until deleted |
| Logs | Job status in the UI | Troubleshooting | Local list in `state.json`; do not put passwords in log text | Until uninstall / log rotation in the app |

Installation parameters do not include NAS username, SMB password, or UGOS API password. The app accesses **only** the folders you grant in App Center / Settings, plus the app data directory.

The admin UI talks to the backend over the NAS HTTP proxy. Passwords, usernames, IP addresses, MAC addresses and device IDs are not sent as plaintext: the browser encrypts them with RSA-OAEP (SHA-256) and the server rejects plaintext. **SMB passwords and the backup archive password are not returned on GET `/api/state`.** The UI shows only a `hasPassword` flag. Empty password fields keep the stored secret. Do not expose port 29140 to the public Internet.

On first open the app shows a privacy dialog (**I agree** / **Decline**). Credentials are stored only after Agree. Decline clears stored SMB and backup passwords; local copies still work.

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

- **Access / portability:** copy the app data folder (`state.json`).
- **Correction:** change values in the app UI, or delete devices/jobs.
- **Deletion:** uninstall the app (this removes the package data directory), or delete individual devices/jobs in the UI.
- **Restrict / object:** remove SMB devices; clear the backup password; or uninstall.

## 6. Storage period

Local files remain until you delete them or **uninstall** the app. Uninstall removes the package directory, including `state.json` (connections, jobs, backup password). There is no Runlevel cloud retention. Backup archive files you already wrote to a folder stay there until you delete them yourself.

## 7. Security

- Native UGOS service (`open_type: inner`). Admin-only (`only_admin: true`).
- Network permission `NETWORK.ACCESS_INTERNET` is declared for SMB and Wake-on-LAN on your LAN.
- Optional backup archives are encrypted with AES-256-CTR and HMAC-SHA256 (password via PBKDF2). A forgotten archive password cannot be recovered.
- Do not expose the app port to the public Internet.

## 8. Host access

- No Docker, no `docker.sock`, no privileged container.
- Only folders you grant (`NAS_FOLDER`, optional `HDD_FOLDER`) plus the app data directory.
- Entire `/home`, `/volume1`, and `/volume2` trees are **not** mounted unless you grant them.

## Contact

Ivica Kampic / Runlevel  
E-mail: runlevel1977@posteo.de  
Registered / office address:  
Ivica Kampic  
Runlevel  
Leipziger Str. 33  
89537 Giengen  
Deutschland
