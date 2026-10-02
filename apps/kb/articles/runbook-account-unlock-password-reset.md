---
title: "Runbook: unlock an account / reset a password / reset MFA"
category: Account & Access
audience: internal
keywords: runbook, unlock account, reset password, admin reset, verify identity, entra id, azure ad, active directory, mfa reset, revoke sessions, lockout source
summary: Technician procedure for unlocking accounts and resetting passwords or MFA — including mandatory identity verification.
---
## 1. Verify identity first (mandatory)

Password and MFA resets are the #1 target of social-engineering attacks. **Never reset based on an email or chat alone.**

- In person with photo ID, **or**
- Call the user back on the phone number **stored in their HR/directory record** (not a number they give you), **or**
- Confirmation from their manager through a known channel.

Record in the ticket (internal note) **how** identity was verified.

## 2. Unlock the account

- **Microsoft Entra ID (cloud):** Entra admin center → Users → select user → check **Sign-in logs** for the failure reason. Smart lockout clears automatically after the lockout period; a password reset also clears it.
- **On-premises Active Directory:** Active Directory Users and Computers → user → **Account** tab → tick **Unlock account**. Or PowerShell: `Unlock-ADAccount -Identity username`.

**Find the lockout source** if it recurs: check sign-in logs (cloud) or event ID `4740` on the domain controller (AD) for the device/IP causing failures. Usually an old password on a phone, mapped drive, or second PC.

## 3. Reset the password

- Set a **temporary** password and tick **require change at next sign-in**.
- Give the temporary password **verbally or via a separate channel** — never in the same email thread as the username, never in the ticket.
- Remote users on AD-joined laptops: have them connect to VPN, then lock/unlock to sync the new password.

## 4. Reset MFA (lost/new phone)

- Entra admin center → user → **Authentication methods** → delete the old methods (or **Require re-register MFA**).
- Consider issuing a **Temporary Access Pass** so the user can register the new device.
- **Revoke sessions** (user → **Revoke sessions**) if the old device is lost or compromise is suspected.

## 5. Suspected compromise?

If the user didn't cause the lockout, received unexpected MFA prompts, or sign-in logs show unfamiliar locations: reset password, **revoke sessions**, review mailbox **inbox rules and forwarding**, and follow "Runbook: security incident first response".

## 6. Close the ticket

Confirm with the user that they can sign in, remind them to update the password on phones/other devices, and link the "Account locked" KB article in the resolution note.
