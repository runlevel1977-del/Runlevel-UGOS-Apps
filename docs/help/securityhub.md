# Security Hub — User Guide

**App ID:** `com.runlevel.securityhub`  
**Port:** 29130  
**Publisher:** Runlevel  
**Support:** runlevel1977@posteo.de · [Issues](https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues)

## What it does

Read-only security overview for administrators: login/auth activity from system and UGOS logs (SSH, web/app logins, SMB audit where available). Does not change firewall or block lists.

## Install / configure

1. Install **Docker** suite.
2. Install **Security Hub**.
3. Set **Data directory** (e.g. `/volume1/docker/security-hub/data`).
4. Optional: NAS IP + UGOS API user/password for related metrics.
5. Open the app (admin only).

## Core usage

1. Open Security Hub.
2. Review recent login / auth events.
3. Filter or refresh as needed.
4. Check language / display options in settings.
5. Use footer Help / Support if something looks wrong.

## Tips

- Display may include client IPs and usernames — admin eyes only.
- Read-only: no modifications to logs or firewall.
- Do not expose port 29130 to the internet.
