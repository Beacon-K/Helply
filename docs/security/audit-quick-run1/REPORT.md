# Helply security audit - quick profile, run-1

## 1. Run summary

| Item | Value |
|---|---|
| Profile | quick (one hunter wave, one final critic pass) - a **partial pass**, not complete coverage |
| Scope | whole repository (`apps`, `agent`, `config`, launch scripts); demo seed data and tests excluded |
| Budget | none set; agents spent versus planned: 0 delegated agents (see below) |
| Source ref | `3aaf546`, worktree dirty (sign-in throttle, sign-in record and login template changes were uncommitted) |
| Execution policy | source-only. No OS-enforced sandbox exists on this Windows host, so no target code was run |
| Prior runs | none for this skill. A separate penetration test (2026-10-05) covered deployment and configuration; it is not repeated here |
| Run status | **incomplete**, reason `independent_verifiers_not_run` |

**Deviations from the skill, stated plainly.** The skill expects separate delegated agents for reconnaissance, hunting, the critic and fresh verifiers. This session's rules do not allow spawning sub-agents unless asked, so the parent performed those roles itself in sequence. That means no record here has the independent verification the skill requires for `confirmed`. Every lead is therefore `needs_validation`, and none has a severity. The two validators refuse to read files on Windows because the OS no-follow protection is unavailable, so both were run through their exported `validateDocument` functions on the parent's own files; both report zero errors.

## 2. Security posture

The application code holds up well. Object-level access control, administrator-only views, CSRF, output escaping, the agent endpoint and redirect handling all check out in source. The leads below are narrow: one weakness in the sign-in throttle added earlier today, one abuse path on the stock password-reset view, one unscoped suggestion list for technicians, and a Windows installer permission gap. No lead is a confirmed vulnerability.

## 3. Confirmed findings

None. (No candidate could be independently reproduced under the skill's execution rules.)

## 4. NEEDS VALIDATION

| Lead | Repository trace | Exact blocker | Bounded local next step | Owner-observed check |
|---|---|---|---|---|
| Sign-in throttle counts compatibility spellings of a username separately (`accounts-throttle-username-normalization-bypass`) | `apps/accounts/forms.py:13` -> `apps/accounts/throttle.py:40,55` -> `apps/accounts/forms.py:19` | No sandbox to run a dummy-account check; Django's NFKC step lives in the installed library | Throw-away database, one dummy user, wrong passwords with different Unicode spellings from one address, compare with the exact spelling | none needed |
| Password reset form has no per-address or per-source limit (`accounts-password-reset-email-flood`) | `config/urls.py:16` -> `apps/accounts/forms.py:29` -> `config/settings.py:191` | No sandbox; mail-provider quota and forwarding are deployment facts | In-memory mail backend, one dummy user, ten posts, count queued messages | Check the Brevo plan's daily limit and whether demo-address mail is forwarded to a real mailbox |
| Similar-ticket suggestions are not limited to tickets the technician may open (`ai-similar-tickets-ignore-visibility`) | `apps/tickets/views.py:71` -> `apps/ai/services.py:88-89` -> `templates/tickets/detail.html:89` | No sandbox; depends on live data | Two groups, one resolved ticket each, an uncategorised open ticket assigned to a technician of the first group; see whether the other group's title is listed | List open uncategorised tickets assigned to technicians |
| Windows agent folder not locked down (`agent-windows-install-dir-writable-by-users`) | `agent/install.ps1:67,99,102` -> `agent/helply_agent.py:16` | Installer and planting cannot be run here; effective ACL on a monitored host is a deployment fact | Disposable Windows machine, run the installer with a dummy token, read the folder ACL, test whether a standard user can create a file (no executable content) | Read the ACL of `C:\ProgramData\HelplyAgent` on each monitored Windows server |

Detail for each lead is in `NEEDS-VALIDATION.md`. One supporting observation: a probe folder created under `C:\ProgramData` on this server inherited an ACE giving `BUILTIN\Users` create-file and create-folder rights.

## 5. Hardening notes and positive patterns

**Hardening (not findings):**
- `HELPLY_ENVIRONMENT` defaults to development, which turns DEBUG on and uses a fixed development key unless a launcher overrides it (`config/settings.py:39-50`). The public launcher overrides it.
- `start-online.bat` makes a new secret on every start, which ends all sessions and unused one-time links, and hands the tunnel token and secret to every child process through the environment.
- `start-online.bat` tells the operator to download `cloudflared.exe` with no checksum step.
- The Linux and Windows installers fetch the agent from the Helply server and check only that it looks like Python; there is no checksum or signature.
- The ingest endpoint has no request limiter (token guessing is impractical at 256 bits).
- Ticket transitions are check-then-act without a row lock; a concurrent double submit can record a transition twice.

**Positive source patterns:** every ticket view resolves objects through `visible_tickets`; internal notes are forced off for non-agents; the ticket asset field is limited to the requester's own assets; agent reports are authenticated, size-capped and clamped field by field; stored text is escaped, with `json_script` for data handed to JavaScript; stored redirects go through a host check; the last administrator cannot be removed or demote themself; departments with people and teams that own categories cannot be deleted; no secrets are in tracked files or history.

## 6. Coverage summary (from the ledger)

| Status | Units |
|---|---|
| covered | 7 (ticket access control, agent ingest, KB and dashboard rendering, deployment configuration, administrator views, notification redirects, Linux installer) |
| candidate | 4 (the leads above) |
| blocked | 0 |
| deferred | 4 (`quick_profile_final_critic`) |

**Final critic result (parent-performed).** Four gaps were accepted and recorded as deferred, not assigned: concurrent ticket transitions, the management commands and demo guard, Django admin registrations for assets, KB and SLA, and the setup and tools launch scripts. This is a quick pass; it does not imply the rest of the repository is clean.
## 7. Follow-up (2026-10-07)

Two leads were fixed in the working tree after this run, with regression tests, but were not re-verified by an independent verifier: ccounts-throttle-username-normalization-bypass (counter key now NFKC-normalises, pps/accounts/throttle.py) and ccounts-password-reset-email-flood (new per-address and per-visitor limit, ThrottledPasswordResetForm). The ledger and findings files in this folder keep the original run state.
