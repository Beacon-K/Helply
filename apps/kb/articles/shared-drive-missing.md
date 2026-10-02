---
title: Shared network drive missing or not accessible
category: Files & Storage
audience: everyone
keywords: shared drive, network drive, mapped drive, s drive, drive letter missing, red x drive, file server, cannot access, network path not found, unc path
summary: Get a mapped network drive (like S: or P:) back when it's missing, shows a red X, or says it can't be reached.
---
## Symptoms

- A drive letter (e.g. `S:`) is missing from **This PC**.
- The drive shows a **red X** or "Disconnected network drive".
- "Windows cannot access \\server\share" or "The network path was not found".

## Quick fixes

1. **Working remotely? Connect to the VPN first**, then wait 30–60 seconds. Network drives usually only work on the office network or VPN.
2. **Double-click the drive** — a red X often just means Windows hasn't reconnected yet since startup.
3. **Open the path directly**: press `Windows + R`, type the full path (e.g. `\\fileserver\shared`) and press Enter. If this works, only the drive letter is missing.
4. **Restart the computer** while on the office network or VPN — drive mappings are usually set up at sign-in.

## Map the drive again (Windows)

1. Open File Explorer → right-click **This PC** → **Map network drive…** (Windows 11: `...` menu → Map network drive).
2. Pick the drive letter your team uses.
3. Enter the folder path (ask a colleague or IT for the exact path).
4. Tick **Reconnect at sign-in** → **Finish**.

## "Access denied"

You can see the drive but not open a folder → you may not have permission. See "Request access to a folder, app, or shared mailbox".

## Asked for a username and password?

Your saved credentials may be out of date after a password change. Enter your work username in the format your company uses (e.g. `COMPANY\username` or your email) and your current password. Remove old entries in **Credential Manager** → Windows Credentials if the prompt keeps returning.

## Open a ticket if

- Several people can't reach the drive → mark **Impact: High** (the file server may be down).
- Only you, after the steps above → include the drive letter, the full path, the exact error, and whether you're in the office or on VPN.

> **Tip:** Many small businesses are moving shared drives to SharePoint / Teams, which works anywhere without VPN. Ask IT if your team's files are available there.
