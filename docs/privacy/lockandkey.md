> Public privacy policy for UGREEN App Center.
> Repository: https://github.com/runlevel1977-del/Runlevel-UGOS-Apps

# Lock & Key — Privacy & Security Summary

**App ID:** `com.runlevel.lockandkey`  
**Publisher:** Runlevel  
**Version:** 0.1.21  

## Data stored locally (on the NAS)

Under the user-chosen **Data directory** (`DATA_PATH`, mounted as `/data` in the container):

| File | Content |
|------|---------|
| `vaults.json` | Vault registry (folder paths, seal status, USB binding hashes, file counts) |
| `jobs.json` | Background job state (seal/unlock progress) |
| `lockkey.log` | Application log |
| `meta.json` | Deleted-vault blocklist and app metadata |

**Encryption keys are not stored on the NAS.** After sealing, the user downloads the key file (`lockkey_<id>.lk`) or writes it to a USB stick. Without the key file (and optional password), encrypted data cannot be recovered.

## User data on shared volumes

The app encrypts files in user-selected folders on **Volume 1** and **Volume 2** (and optional UGOS folder shortcut):

- Encrypted files use suffix `.lkenc`
- Marker `.lockkey-sealed` and manifest `.lockkey-manifest` in the vault folder
- Original plaintext files are removed after a successful seal

## Network behavior

- **No outbound connections** to Runlevel or third-party analytics.
- Web UI is served on port **29135** (admin access only via UGOS).
- Optional link in the UI points to **Ugreen NAS Admin** on GitHub (user-initiated).

## Host access

| Mount | Access | Purpose |
|-------|--------|---------|
| `/volume1`, `/volume2` | read/write | User folders to seal/unlock |
| `${NAS_DATA_ROOT}` → `/mnt/ugos` | read/write | Folder picker shortcut |
| `/mnt/@usb` | read/write | USB key file read/write; stick may be formatted before key write |
| `/dev`, `/sys` | read-only | USB device identification |
| `/var/packages/com.runlevel.lockandkey` | read-only | Package metadata |

The app can **format or wipe USB sticks** when writing a key file (FAT32, single key per stick). This affects only removable USB media selected by the administrator.

## Access control

- App is **admin-only** (`only_admin: true`).
- Flask UI has no separate login — protection relies on UGOS admin session and network access to port 29135.
- Do not expose port 29135 to the internet without additional protection.

## Data retention

- Registry and logs remain under `DATA_PATH` until the user deletes that folder.
- Uninstalling the app typically leaves `DATA_PATH` and encrypted `.lkenc` files on the NAS intact.

## Contact

Developer contact for privacy inquiries: runlevel1977@posteo.de (Ivica Kampic, Runlevel)
