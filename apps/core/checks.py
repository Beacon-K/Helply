"""Production readiness checks, shown by `python manage.py check --deploy`."""
from django.conf import settings
from django.core.checks import Tags, Warning, register
from django.db import connection


@register(Tags.security, deploy=True)
def production_checks(app_configs, **kwargs):
    if not settings.IS_PRODUCTION:
        return []
    issues = []
    if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
        issues.append(Warning(
            "Emails are only printed to the console, so nobody receives notifications or password-reset emails.",
            hint="Set DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend and the EMAIL_* settings in .env.",
            id="helply.W001",
        ))
    if connection.vendor == "sqlite":
        issues.append(Warning(
            "Production is using SQLite, which handles many people writing at once poorly.",
            hint="Use PostgreSQL (POSTGRES_* settings in .env) for production.",
            id="helply.W002",
        ))
    if settings.HELPLY_SITE_URL.startswith("http://127.0.0.1"):
        issues.append(Warning(
            "HELPLY_SITE_URL still points to this computer, so links in emails will not work for other people.",
            hint="Set HELPLY_SITE_URL=https://your-domain in .env.",
            id="helply.W003",
        ))
    return issues
