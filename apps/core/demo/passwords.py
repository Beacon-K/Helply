"""Demo account passwords - kept out of the source code.

Passwords are always stored hashed in the database (Django's PBKDF2). The only
plaintext is the shared password the demo loader gives new demo accounts, and
that lives in the local, git-ignored .env file as HELPLY_DEMO_PASSWORD. If it
is missing, a random one is generated and saved there on first use.
"""
import os
import secrets

from django.conf import settings

ENV_KEY = "HELPLY_DEMO_PASSWORD"


def _random_password():
    return "helply-" + secrets.token_urlsafe(9)


def demo_password():
    """The shared password for demo accounts on this installation."""
    password = os.environ.get(ENV_KEY)
    if not password:
        password = _random_password()
        env_file = settings.BASE_DIR / ".env"
        with env_file.open("a", encoding="utf-8") as f:
            f.write(f"\n# Shared password for the demo accounts (generated automatically).\n{ENV_KEY}={password}\n")
        os.environ[ENV_KEY] = password
    return password


def demo_users():
    from apps.accounts.models import User

    from .people import USERS

    return list(User.objects.filter(username__in=[u[0] for u in USERS]).order_by("role", "username"))


def reset_to_shared():
    """Give every demo account the shared demo password again (for local demos)."""
    password = demo_password()
    for user in demo_users():
        user.set_password(password)
        user.save(update_fields=["password"])
    return password


def randomize():
    """Give every demo account its own random password (for demos on the public internet)."""
    result = []
    for user in demo_users():
        password = _random_password()
        user.set_password(password)
        user.save(update_fields=["password"])
        result.append((user, password))
    return result
