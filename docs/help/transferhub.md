# Transfer Hub — User Guide

**App ID:** `com.runlevel.transferhub`  
**Port:** 29100  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Copy or sync folders between the NAS folder you select at install, USB, and SMB devices on the LAN. Profiles, schedules, and live job progress.

## Install / configure

1. Install **Docker** suite.
2. Install **Transfer Hub**.
3. Set **UGOS folder** to the directory you want to copy from/to (this is the **only** NAS folder mounted — not the whole volume or `/home`). App password and profiles are stored in the package directory and are **removed on uninstall**.
4. Optional: LAN scan CIDR / extra hosts (not passwords).
5. Open the app. First screen: **privacy consent** (Agree and Decline). Then set an app password.

## Core usage

1. Open Transfer Hub, confirm privacy, sign in.
2. Add a **device** (SMB host + credentials). The password is sent encrypted (`password_enc`), not as HTTP plaintext.
3. Create a **profile**: source → destination, options (copy/sync).
4. Run once (**Start**) or enable a schedule.
5. Watch job progress and stop if needed.

## Tips

- Pick a UGOS folder that actually contains the data you want to copy (e.g. your backup share).
- Prefer dedicated SMB accounts with minimal share rights.
- Uninstalling the app clears the app password and profiles.
- Footer: Help, Privacy, Support.
