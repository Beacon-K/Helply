# Needs validation

Unresolved leads with no severity. Each names the exact blocker and a bounded plan; none is a live-test instruction.

## Password reset form has no per-address or per-source limit
Fingerprint: `accounts-password-reset-email-flood`

Anyone can submit the password reset form repeatedly for the same address. Each submission for a real account sends an email through the shared mail provider, which can flood a mailbox and use up the provider's daily quota that real notifications also need.

**Claimed root cause:** The stock Django reset view is included without a request limiter; the throttle was added only to the two sign-in forms.

**Trace**
1. `entrypoint` `config/urls.py:16` (urlpatterns): django.contrib.auth.urls exposes accounts/password_reset/ to anonymous visitors.
2. `propagation` `apps/accounts/forms.py:29` (ThrottledAuthenticationForm): Throttling is attached to the sign-in forms only.
3. `sink` `config/settings.py:191` (EMAIL_BACKEND): Reset messages are delivered through the configured SMTP provider.

**Evidence**
- `config/urls.py:15`: Only the login route is wrapped with the throttled form.
- `config/settings.py:191`: Outgoing mail uses a single shared provider account.

**Blockers**
- The audit's sandbox rule forbids running the target here, and no provider quota fact is source-visible.
- The provider's daily limit and the mailbox forwarding behind @helply.work addresses are deployment facts.

**Resolution plan**
- Local: With the in-memory mail backend and a dummy user, post the reset form ten times for one address and count queued messages.
- Deployment: The owner checks the Brevo plan's daily sending limit and whether any reset mail for the demo addresses is forwarded to a real mailbox.

## Sign-in throttle counts compatibility spellings of a username separately
Fingerprint: `accounts-throttle-username-normalization-bypass`

The sign-in throttle keys its counters on the lower-cased raw username, but Django authenticates the NFKC-normalised username. Spellings such as fullwidth letters are different counter keys yet the same account, so the per-username limits can be dodged. Only the per-address limit remains.

**Claimed root cause:** throttle.clean_username normalises case and whitespace only, not Unicode compatibility forms, while the form field normalises with NFKC before authentication.

**Trace**
1. `entrypoint` `apps/accounts/forms.py:13` (ThrottleMixin.clean): The username is read from the raw POST data before the form field normalises it.
2. `propagation` `apps/accounts/throttle.py:40` (clean_username): The key is strip().lower() of the raw value.
3. `propagation` `apps/accounts/throttle.py:55` (blocked_for): Per-username and per-username-and-address counters filter on that key.
4. `sink` `apps/accounts/forms.py:19` (ThrottleMixin.clean): super().clean() authenticates the NFKC-normalised username, so a differently spelled key still tests the same account.

**Evidence**
- `apps/accounts/throttle.py:40`: No NFKC step in the counter key.
- `apps/accounts/forms.py:13`: Raw self.data value is used, not cleaned_data.

**Blockers**
- No OS-enforced sandbox is available on this Windows host, so the dummy-account check could not be run.
- The NFKC behaviour of Django's UsernameField is in the installed library, outside the repository.

**Resolution plan**
- Local: In a throw-away database create one dummy user. Send more than HELPLY_LOGIN_MAX_FAILURES wrong passwords using different compatibility spellings of that username from one address and check whether the password is still evaluated after the limit; then repeat with the exact spelling and compare.

## Windows agent folder is not locked down, so its script directory may be writable by standard users
Fingerprint: `agent-windows-install-dir-writable-by-users`

The Windows installer creates the agent folder under C:\ProgramData without setting its permissions and protects only the config file. A new folder there inherits rights that let standard users create files. The scheduled task runs the agent script as LOCAL SERVICE or SYSTEM with that folder as its script directory, so a file a standard user plants there with a standard-library module name could be imported first.

**Claimed root cause:** install.ps1 does not remove inherited user write rights from the agent directory, and Python puts the script directory first on its import path.

**Trace**
1. `entrypoint` `agent/install.ps1:67` (directory creation): New-Item creates the agent folder with the inherited ProgramData permissions.
2. `propagation` `agent/install.ps1:99` (icacls): Only agent.conf receives a restricted ACL.
3. `propagation` `agent/install.ps1:102` (scheduled task action): pythonw runs the script from the agent folder as the working directory.
4. `sink` `agent/helply_agent.py:16` (imports): The agent imports standard-library modules; the script directory is searched before the standard library.

**Evidence**
- `agent/install.ps1:99`: icacls is applied to the config file, not the directory or script.
- `agent/install.ps1:104`: The task principal is LOCAL SERVICE, or SYSTEM when Python is per-user.

**Blockers**
- The audit's sandbox rule forbids running the installer or planting files here.
- A standard user on the monitored host and the effective ACL of the installed folder are deployment facts.

**Resolution plan**
- Local: On a disposable Windows machine run the installer with a dummy token, read the folder ACL with icacls, and check whether a standard user can create a new file in it. Do not plant executable content.
- Deployment: On each monitored Windows server, the owner reads the ACL of C:\ProgramData\HelplyAgent and lists the local users who are not administrators.

## Similar-ticket suggestions are not limited to tickets the technician may open
Fingerprint: `ai-similar-tickets-ignore-visibility`

The panel shown to technicians lists reference and title of resolved or closed tickets chosen from the whole ticket table. When the open ticket has no category the pool is not narrowed at all, so titles from other support groups can appear.

**Claimed root cause:** similar_tickets() does not apply the viewer's visibility scope, and the category filter is skipped when the ticket has no category.

**Trace**
1. `entrypoint` `apps/tickets/views.py:71` (ticket_detail): Agents get context['similar'] from the viewed ticket.
2. `propagation` `apps/ai/services.py:88` (similar_tickets): The candidate pool is every resolved or closed ticket.
3. `propagation` `apps/ai/services.py:89` (similar_tickets): The pool is narrowed by category only when the ticket has one.
4. `sink` `templates/tickets/detail.html:89` (similar panel): Reference and title of each match are rendered for the technician.

**Evidence**
- `apps/tickets/selectors.py:6`: visible_tickets defines who may open which ticket, but the suggestion query never uses it.
- `apps/ai/services.py:91`: Scoring runs over the first 500 unscoped candidates.

**Blockers**
- The audit's sandbox rule forbids running the target here, so no dummy-tenant check was run.
- Whether production data has uncategorised or cross-group tickets in the pool depends on live data.

**Resolution plan**
- Local: In a throw-away database create two support groups with a resolved ticket in each, and an uncategorised open ticket assigned to a technician of the first group; open it as that technician and see whether the other group's resolved ticket title is listed.
- Deployment: The owner lists open uncategorised tickets assigned to technicians to see how often the unscoped pool is used.
