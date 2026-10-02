---
title: OneDrive not syncing
category: Files & Storage
audience: everyone
keywords: onedrive, sync, not syncing, sync pending, sync error, red x, cloud icon, sharepoint sync, files not updating, conflict, duplicate files, files on demand
summary: Understand the OneDrive status icons and fix files that are stuck, conflicting, or not showing up on your other devices.
---
## Read the icons

In File Explorer, each file and folder shows a status icon:

- ☁️ **Blue cloud** — online only; downloads when you open it (saves disk space).
- ✅ **Green tick (outline)** — available on this device.
- ✅ **Solid green circle** — "Always keep on this device".
- 🔄 **Arrows** — syncing in progress.
- ❌ **Red X / red circle** — sync problem with that file.

The **OneDrive cloud icon** on the taskbar (or Mac menu bar) shows the overall status. Click it for details and error messages.

## Quick fixes

1. **Click the OneDrive icon** and read the message — it often says exactly what's wrong (e.g. "file is open", "sign in required", "storage full").
2. **Close the file** in all apps — open files can't sync until closed.
3. **Pause and resume:** OneDrive icon → ⚙️ **Help & Settings** → **Pause syncing** → 2 hours, then **Resume syncing**.
4. **Sign in** if OneDrive says it needs you to.
5. **Restart OneDrive:** OneDrive icon → ⚙️ → **Quit OneDrive**, then open OneDrive from the Start menu.
6. **Restart the computer.**

## Common causes of red X errors

- **File name problems:** names with characters like `" * : < > ? / \ |`, or starting with a space. Rename the file.
- **Path too long:** very deep folder structures. Move the file to a shallower folder or shorten folder names.
- **Very large files** or blocked file types — check the error message.
- **No permission:** you don't have edit rights to the shared folder you're syncing.
- **Disk full** on your computer — see "Low disk space: how to free up room".

## Duplicate files with your computer's name added

e.g. `Budget-LAPTOP-123.xlsx`. This is a **sync conflict**: the file was changed in two places at once. Open both, keep the right content in one, and delete the other.

> **Tip:** Opening files directly from OneDrive/SharePoint (with AutoSave on) lets several people edit at the same time without conflicts.

## Open a ticket if

The error persists. Include a screenshot of the OneDrive status window (click the icon → **View sync problems**) and the file path.
