---
title: Outlook not sending or receiving email
category: Email
audience: everyone
keywords: outlook, email, not receiving, not sending, stuck in outbox, disconnected, working offline, send receive, bounce, undeliverable, ndr, missing email
summary: Fix emails stuck in the Outbox, new mail not arriving, "Disconnected / Working offline", and bounce-back messages.
---
## First: is it Outlook or your mailbox?

Open **Outlook on the web** (for Microsoft 365: `https://outlook.office.com`) in a browser.

- Email works there → the problem is the Outlook app on your computer. Continue below.
- Email is missing there too → the problem is with the mailbox or the sender. Skip to "Email from a specific person is missing".

## Check the status bar

Look at the bottom of the Outlook window:

- **Working Offline** → go to the **Send / Receive** tab and click **Work Offline** to turn it off.
- **Disconnected** or **Trying to connect…** → check your internet, then close and reopen Outlook.
- **Need password** → click it and sign in again (see "Outlook keeps asking for my password").

## Emails stuck in the Outbox

1. Check the **attachment size** — most mail systems reject messages over about **20–25 MB**. Share large files as a **OneDrive / SharePoint link** instead.
2. Open the Outbox, **drag the stuck message to Drafts**, open it, and click Send again.
3. Close Outlook completely (check it's gone from Task Manager), then reopen it.

## New mail not arriving

1. Check the **Junk Email** folder, and the **Other** tab if you use Focused Inbox.
2. Check your **Rules**: File → Manage Rules & Alerts — a rule may be moving messages to another folder.
3. Check your mailbox isn't full (see "Mailbox full: how to free up space").
4. Search for the message using the sender's address — it may have been filed or archived.

## Email from a specific person is missing

- Ask the sender whether they got a **bounce-back** ("undeliverable") message and to forward it to you — it explains exactly why delivery failed.
- Check the address was spelled correctly.
- It may be in **quarantine** — include the sender's address and the approximate time sent in your ticket, and IT can check.

## I received an "Undeliverable" message

Read the message — it usually says why: mistyped address, recipient's mailbox full, or the message was too large. Correct it and resend. If it says your message was blocked as spam, open a ticket and attach the bounce message.

## Quick repair

Still broken in the app but fine on the web? Close Outlook, then restart your computer. If that fails, open a ticket — IT may rebuild your Outlook profile.

Include in your ticket: screenshots of the status bar or error, whether Outlook on the web works, and example senders/times of missing messages.
