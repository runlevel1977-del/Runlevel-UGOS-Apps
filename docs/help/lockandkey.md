# Lock & Key — User Guide

**App ID:** `com.runlevel.lockandkey`  
**Port:** 29135  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Encrypt selected folders on Volume 1/2 into sealed vaults. The encryption key is **not** kept on the NAS — download the key file or store it on USB. Without the key (and optional password), sealed data cannot be recovered.

## Install / configure

1. Install **Docker** suite.
2. Install **Lock & Key**.
3. Set **Data directory** (e.g. `/volume1/docker/lock-and-key/data`).
4. Optional: UGOS folder shortcut, UGOS API credentials.
5. Open the app (admin only).

## Core usage — seal (encrypt)

1. Open Lock & Key.
2. Choose a folder on Volume 1 or 2.
3. Start **Seal** / encrypt job.
4. When finished: **download the key file** (`.lk`) and/or write it to USB.
5. Store the key offline in a safe place. Do not lose it.

## Core usage — unlock

1. Provide the key file (upload or USB).
2. Enter password if one was set.
3. Run unlock; wait for job completion.
4. Verify files are readable again.

## Critical warnings

- Losing the key file means permanent data loss for sealed content.
- Test with a small non-critical folder first.
- Do not expose port 29135 to the internet.
