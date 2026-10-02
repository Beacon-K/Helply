"""Safety checks for the demo-data commands, so they can never damage a real installation."""
from django.conf import settings
from django.core.management.base import CommandError

from .people import USERS

DEMO_USERNAMES = {u[0] for u in USERS}


def require_demo_allowed(action):
    """Refuse demo-data commands in production."""
    if settings.IS_PRODUCTION:
        raise CommandError(f"{action} is disabled because HELPLY_ENVIRONMENT=production. "
                           "Demo data must never be loaded into a production system.")


def require_demo_database(action, force=False):
    """Refuse to wipe data if the database contains anyone who is not a demo account.

    A second line of defence in case HELPLY_ENVIRONMENT was not set on a real system.
    """
    require_demo_allowed(action)
    from apps.accounts.models import User

    real_users = list(User.objects.exclude(username__in=DEMO_USERNAMES).values_list("username", flat=True)[:5])
    if real_users and not force:
        raise CommandError(
            f"{action} would delete data, but this database has accounts that are not demo accounts "
            f"({', '.join(real_users)}). It looks like a real system, so nothing was changed. "
            "Use --force only if you are sure this is a throw-away demo database."
        )
