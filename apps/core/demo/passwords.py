"""Demo account passwords - kept out of the source code.

Passwords are always stored hashed in the database (Django's PBKDF2); a hash cannot be turned back into
the password. A demo account gets its password exactly once, when the account is created, and nothing
resets it afterwards: after that the password belongs to the person. Only an explicit command
(demo_passwords --rotate / --shared, or reset-demo.bat) ever changes existing demo passwords.

How a new account gets its first password:
  * Normal (local) use: the shared HELPLY_DEMO_PASSWORD from the git-ignored .env file. If it is missing,
    a random one is generated and saved there on first use.
  * Public site (HELPLY_PUBLIC_HOST is set): its own random password, appended to demo-passwords.txt on
    this drive (git-ignored). The shared password must never protect accounts reachable from the internet.
"""
import os
import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password

ENV_KEY = "HELPLY_DEMO_PASSWORD"
LIST_HEADER = ("Helply demo accounts - first passwords, written once when each account is created.\n"
               "People who change their own password make this file out of date for them. Keep it private; "
               "it is not committed to git.\n\n")
_shared = {}


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


def password_list():
    return settings.BASE_DIR / "demo-passwords.txt"


def _record(username, role, password):
    path = password_list()
    new = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if new:
            f.write(LIST_HEADER)
        f.write(f"{username:<12} {role:<14} {password}\n")


def initial_hash(username, role):
    """The password hash for a brand-new demo account (see the module docstring)."""
    if settings.HELPLY_PUBLIC_HOST:
        password = _random_password()
        _record(username, role, password)
        return make_password(password)
    password = demo_password()
    if _shared.get("password") != password:  # hashing is deliberately slow: do it once for all new accounts
        _shared.update(password=password, hash=make_password(password))
    return _shared["hash"]


def demo_users():
    from apps.accounts.models import User

    from .people import USERS

    return list(User.objects.filter(username__in=[u[0] for u in USERS]).order_by("role", "username"))


def reset_to_shared():
    """Give every demo account the shared demo password again (explicit, for local demos)."""
    password = demo_password()
    for user in demo_users():
        user.set_password(password)
        user.save(update_fields=["password"])
    return password


def randomize():
    """Give every demo account its own new random password (explicit rotation). Returns [(user, password)]."""
    result = []
    for user in demo_users():
        password = _random_password()
        user.set_password(password)
        user.save(update_fields=["password"])
        result.append((user, password))
    return result
