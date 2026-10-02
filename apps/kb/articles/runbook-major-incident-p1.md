---
title: "Runbook: major incident (P1) handling"
category:
audience: internal
keywords: runbook, major incident, p1, outage, critical, everyone affected, escalation, communication, post incident review, sla
summary: How IT handles a P1 / major incident — who does what, how to communicate, and the post-incident review.
---
## What counts as a major incident?

Any **P1** in Helply (Impact High + Urgency High), for example:

- Internet or Wi-Fi down for the whole office.
- Email, the file server, or a business-critical system (POS, accounting, booking) down for many users.
- A security incident with active impact (ransomware, compromised admin account).

## First 15 minutes

1. **One ticket, one owner.** Pick the first/best P1 ticket as the master; the supervisor assigns an **incident owner** (coordinates) — separate from the technician(s) fixing it if staff allow.
2. **Link duplicates:** comment on duplicate tickets with the master ticket number and resolve them as duplicates, so the queue stays clean.
3. **Acknowledge publicly:** post a short message to staff (email/Teams): what's affected, that IT is working on it, when the next update will be. This stops a flood of new tickets.
4. **Confirm scope:** who/what is affected, since when, what changed recently (updates, config changes, provider notices).

## While working the incident

- **Update the ticket timeline** with internal notes: actions taken and times. Helply records the audit trail — keep it accurate for the review.
- **Communicate every 30–60 minutes**, even if there's no progress ("still investigating, next update at 11:30").
- Check **provider status pages** (ISP, Microsoft 365, cloud apps) and open vendor support cases early.
- **Prefer restoring service over finding root cause** — workaround first (e.g. phone hotspot, backup internet, switch to web app), root cause later.
- Escalate to the business owner/manager if the incident is expected to exceed the **P1 SLA resolution target** — the dashboard's "SLA at risk" panel shows this.

## Resolution

1. Confirm with affected users that service is back.
2. Send a "resolved" message to staff.
3. Resolve the master ticket with a clear resolution note: **cause, fix, duration, workaround used**.

## Post-incident review (within 5 working days)

Short meeting or document covering:

- Timeline (from the ticket history), impact, and SLA met/breached.
- Root cause and contributing factors.
- **Actions to prevent recurrence** — each with an owner and due date (create follow-up tickets).
- Whether a new or updated **KB article** is needed.
