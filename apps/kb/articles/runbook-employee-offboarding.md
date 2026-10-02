---
title: "Runbook: employee offboarding checklist"
category:
audience: internal
keywords: runbook, offboarding, leaver, termination, employee leaving, disable account, remove access, recover laptop, mailbox forwarding, checklist
summary: IT checklist for removing access and recovering equipment when an employee leaves — on time, and without losing company data.
---
## Trigger

A ticket from HR or the manager with: name, last working day and time, whether the departure is **friendly or sensitive**, and instructions for their mailbox and files. For sensitive departures, HR should mark urgency **High** and coordinate the exact time with IT.

## At the agreed time (end of last day)

1. **Disable sign-in** (don't delete the account yet).
2. **Reset the password** and **revoke all sessions** so existing sign-ins on phones and browsers stop working.
3. **Remove MFA methods** and device registrations; remotely wipe **company data** from personal phones (app protection) if applicable.
4. **Remove from groups**, shared mailboxes, Teams ownership, and admin roles. Transfer ownership of Teams/SharePoint sites they owned.
5. Disable **VPN** and any third-party system accounts (accounting software, CRM, payroll portal, social media accounts). Keep a list — small businesses often forget SaaS accounts paid with a card.

## Mailbox and files

6. As instructed by the manager: convert the mailbox to a **shared mailbox** and grant the manager access, and/or set an **automatic reply** with a new contact.
7. Transfer **OneDrive** files to the manager (Microsoft 365 can grant the manager access to the leaver's OneDrive).
8. Remove any **mail forwarding** rules to external addresses.

## Equipment

9. Collect laptop, charger, phone, security keys/badges, and accessories. Check against the **asset register** in Helply (Assets filtered by owner).
10. Set assets to **In stock** (or **In repair** / **Retired**), clear the owner, and wipe/re-image the laptop before reuse.

## Afterwards

11. **Remove the license** once the mailbox is converted/retained (saves cost).
12. After the retention period agreed with the business (e.g. 30–90 days), delete the account per policy.

## Close the ticket

Resolution note: time access was removed, assets recovered (tags), mailbox/OneDrive handling, and any accounts outside Microsoft 365 that were disabled.
