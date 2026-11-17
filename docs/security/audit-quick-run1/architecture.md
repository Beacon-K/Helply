# Helply architecture summary (quick audit, run-1)

**Product and principals.** Helply is an IT service desk for 10 to 100 person companies, written in Django 6.1 with server-rendered templates and a small amount of vanilla JavaScript. Principals: anonymous visitor; employee (own tickets, own devices); technician (tickets of own support groups, assets, cloud servers); administrator (people, SLA, teams, everything); a monitoring agent on a customer-owned server (bearer token per server); the platform operator (launch scripts, .env). Protected resources: ticket and asset data, accounts and password links, the shared SMTP account, the tunnel token and secret key, and the monitoring fleet.

**Comparable baseline.** None source-grounded; the closest family is small self-hosted Django service desks. Severity is calibrated against the stated anchors only.

**Stack and operation.** Python 3.12 or newer, Django, SQLite (WAL) or PostgreSQL, Waitress, WhiteNoise, Cloudflare Tunnel for public access, Brevo SMTP. Launchers are Windows batch files. No OS sandbox is available on this Windows host, so no target code was run: this is a source-only pass, and every candidate that needs execution is a needs_validation lead.

**Entry surfaces.** Sign-in and admin sign-in (accounts/forms.py, config/urls.py); stock password-reset and change views; ticket, KB, asset, notification, people, team, department and SLA views; the agent ingest endpoint and the public agent downloads (monitoring/views.py); the Windows and Linux installers; launch scripts and settings.

**Trust boundaries and strongest control on each.** Row-level scoping for tickets (tickets/selectors.py:visible_tickets) and assets (assets/views.py:visible_assets); role_required for administrator pages (accounts/decorators.py); Django CSRF on every form with ingest as the only exemption; per-server hashed bearer tokens with size and value clamps for reports; escape-before-markup rendering for KB text and json_script for data handed to JavaScript; url_has_allowed_host_and_scheme for stored redirects; ALLOWED_HOSTS plus Secure cookies, SSL redirect and HSTS in public mode; a database-backed sign-in throttle (accounts/throttle.py).

**Starting paths.** apps/accounts, apps/tickets, apps/ai, apps/monitoring, apps/notifications, apps/kb, agent, config, start-online.bat.

**Prior coverage.** No compatible prior ledger exists. A separate penetration test on 2026-10-05 (docs/security) found deployment and configuration issues outside this ledger's source scope (shared initial passwords, public admin path, TLS floor, file permissions); those are not repeated here.

**Companion selection.** WEB-PROTOCOL-AND-AUTH (sessions, account recovery), RESOURCE-EXHAUSTION-AND-AVAILABILITY (mail quota), DESKTOP-MOBILE-AND-LOCAL-IPC (Windows service folder permissions), CLIENT-SIDE (DOM renderers), SUPPLY-CHAIN-AND-RELEASE (agent installer). Excluded: MEMORY-SAFETY-AND-BINARY (no native code), AI-AND-LLM (the classifier is a keyword baseline with no model), PROTOCOLS-RPC-AND-MESSAGING (no RPC or broker), CLOUD-AND-DEPLOYMENT (no IaC), DATA-ISOLATION-AND-LIFECYCLE (single tenant; row scoping covered under Access control).