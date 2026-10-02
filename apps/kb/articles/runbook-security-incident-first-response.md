---
title: "Runbook: security incident first response"
category: Security
audience: internal
keywords: runbook, security incident, compromised account, phishing clicked, malware, ransomware, isolate device, revoke sessions, inbox rules, forwarding, containment, evidence
summary: First-response steps for compromised accounts, malware, and phishing clicks — contain first, preserve evidence, then recover.
---
## Priorities

**Contain → preserve evidence → eradicate → recover → learn.** Treat as **P1** if data, money, or many users are at risk. Thank the reporter — fast reporting must be encouraged, never punished.

## Compromised account (password entered on phishing page, suspicious sign-ins)

1. **Reset the password** and **revoke all sessions** (Entra admin center → user → Revoke sessions).
2. **Reset MFA methods** and review registered devices — attackers often add their own MFA method.
3. Review **sign-in logs** for unfamiliar locations/IPs and the time window of access.
4. Check the mailbox for attacker persistence: **inbox rules** (especially rules deleting or moving messages, or forwarding externally), **forwarding settings**, delegates, and recently **sent items** (phishing sent to contacts).
5. Check **app consents / OAuth apps** granted by the user.
6. If the attacker sent phishing from the account, warn recipients (internal and external) and search/purge the message from other mailboxes.

## Malware or suspicious file opened

1. **Isolate the device**: disconnect Wi-Fi/network (or use your endpoint security's isolate function). **Don't power off** unless ransomware is actively encrypting and isolation isn't possible.
2. Run a full scan with the company's endpoint protection; collect alerts/screenshots.
3. Reset the user's password from a clean device.
4. If in doubt, **re-image** the device rather than trusting a clean-up.

## Ransomware signs

Mass file renames/new extensions, ransom notes, many users reporting inaccessible files: isolate affected devices, **disconnect file shares / sync if spreading**, protect backups (take them offline), and escalate immediately to management. Do not pay or contact attackers without management and legal advice.

## Evidence to keep

The original phishing email (as attachment), sign-in log exports, times of each action, device name, and screenshots. Record everything in the Helply ticket as **internal notes** — the audit trail is your incident timeline.

## Notification

Business owner/management decides on notifying customers, insurers, banks, or regulators. In Canada, breaches of personal information involving a **real risk of significant harm** may need to be reported to the Privacy Commissioner and affected individuals under PIPEDA — escalate to management to decide.

## Afterwards

Hold a short post-incident review (see "Runbook: major incident (P1) handling"), create follow-up tickets, and update user-facing KB articles if the scam was new.
