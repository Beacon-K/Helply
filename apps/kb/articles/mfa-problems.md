---
title: MFA / Authenticator problems (new phone, no code, no prompt)
category: Account & Access
audience: everyone
keywords: mfa, 2fa, multi-factor, two factor, authenticator, microsoft authenticator, verification code, new phone, lost phone, approve sign in, number matching
summary: Fix missing MFA prompts and codes, move the Authenticator app to a new phone, and what to do if you get a prompt you didn't expect.
---
## What is MFA?

Multi-factor authentication (MFA) means signing in needs **something you know** (password) **plus something you have** (your phone). Even if your password is stolen, the attacker can't get in without your phone.

## I'm not receiving the prompt or code

1. Make sure your phone has **internet access** (Wi-Fi or mobile data) — the Authenticator push needs it.
2. Open the **Authenticator app** directly; pending requests often appear inside the app even if the notification didn't.
3. Check the phone's **date and time** are set to automatic. A wrong clock makes 6-digit codes fail.
4. Allow notifications for the Authenticator app in your phone settings.
5. No signal? Use the **6-digit code** shown in the app instead of the push — it works offline.
6. SMS codes delayed? Wait a minute and use only the **latest** code.

## I got a new phone

Do this **before** you wipe or trade in the old phone if you can:

1. On a computer, sign in to your account's security info page (for Microsoft 365: `https://mysignins.microsoft.com/security-info`).
2. Click **Add sign-in method** → **Authenticator app**, then follow the QR-code steps with your new phone.
3. Test it, then delete the old phone from the list.

If the old phone is already gone, open a ticket — IT will reset your MFA registration after confirming your identity (usually by phone or in person).

## I got an MFA prompt I didn't start

> **Warning:** Tap **Deny** / **No, it's not me**. Never approve a prompt you didn't start — this is how attackers get in after stealing a password.

Then immediately:

1. Change your password (see "How to reset a forgotten password").
2. Open a ticket with **Impact: Medium, Urgency: High** saying you received an unexpected MFA prompt.

## Still stuck?

Open a ticket with your phone model, the sign-in method you use (app push, code, or SMS), and the exact error message.
