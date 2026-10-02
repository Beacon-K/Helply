---
title: Outlook or Office keeps asking for my password
category: Email
audience: everyone
keywords: password prompt, keeps asking for password, credentials, sign in again, need password, outlook password, office sign in loop, credential manager
summary: Stop repeated password or sign-in prompts in Outlook, Teams and other Office apps.
---
## Why it happens

Office apps save your sign-in. After a **password change**, an **expired session**, or a problem with the saved credentials, they keep asking again — sometimes in a loop.

## Fixes (try in order)

1. **Type your current password once, carefully**, and tick "Remember me" if offered. If you changed your password recently, make sure you're using the new one.
2. **Check it isn't a fake prompt.** A real Microsoft prompt appears as part of the app. Be suspicious of prompts that arrive from an email link — see "How to recognize and report phishing".
3. **Sign out and back in to Office:** open Word or Excel → click your name/photo at the top right → **Sign out**. Close all Office apps, reopen Outlook and sign in.
4. **Restart your computer**, and connect to the VPN before opening Outlook if you're remote.

## Clear saved credentials (Windows)

1. Close all Office apps (Outlook, Teams, Word, Excel).
2. Search the Start menu for **Credential Manager** → **Windows Credentials**.
3. Under **Generic Credentials**, remove entries that start with `MicrosoftOffice` or mention `outlook` / `office`.
4. Reopen Outlook and sign in when asked.

## Mac

1. Quit all Office apps.
2. Open **Keychain Access**, search for `Microsoft Office` / `Exchange` / `Outlook`, and delete those entries (only these).
3. Reopen Outlook and sign in.

## Still asking?

Open a ticket with a screenshot of the prompt (it shows which service is asking), when it started, and whether you recently changed your password. Repeated prompts can also happen when an account is locked — see "My account is locked".
