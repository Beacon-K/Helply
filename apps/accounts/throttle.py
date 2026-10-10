"""Sign-in and password-reset throttling.

Password reset (bottom of this file): at most HELPLY_RESET_MAX_PER_EMAIL emails per address and
HELPLY_RESET_MAX_PER_IP requests per visitor inside HELPLY_RESET_WINDOW_MINUTES. The page answers the same way
whether or not an email was sent, so it still does not reveal which addresses have accounts, and the shared
mail account cannot be used up by one visitor.

Sign-in throttling: slows down password guessing on /accounts/login/ and /admin/login/.

Failures are written to the database (not memory), so a restart does not reset them and every process
sees the same counts. Three counters use one sliding window (HELPLY_LOGIN_LOCK_MINUTES):

  * the same username from the same address  - HELPLY_LOGIN_MAX_FAILURES        (default 5)
  * the same username from anywhere          - HELPLY_LOGIN_MAX_FAILURES_USER   (default 20)
  * the same address, whatever username      - HELPLY_LOGIN_MAX_FAILURES_IP     (default 30)

A person who mistypes a few times is only held back on their own address, so an attacker cannot lock
a colleague out from elsewhere unless they make dozens of guesses (the per-username limit). While a counter is
over its limit even the correct password is refused, otherwise the lock would not stop guessing. The counters
apply to names that do not exist too, so the lock message never reveals whether an account exists.
"""
import ipaddress
import logging
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginFailure, ResetRequest

log = logging.getLogger("helply.security")


def client_ip(request):
    """The visitor's address. Behind the local Cloudflare tunnel the real one is in CF-Connecting-IP."""
    remote = request.META.get("REMOTE_ADDR", "")
    candidate = remote
    if remote in ("127.0.0.1", "::1"):
        candidate = request.headers.get("CF-Connecting-IP", remote)
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def clean_username(value):
    """The key the counters use. Django signs people in with the NFKC-normalised name, so fullwidth or other
    compatibility spellings of one username must land on the same counter; otherwise each spelling would get
    its own allowance of wrong guesses."""
    return unicodedata.normalize("NFKC", value or "").strip().lower()[:150]


def _wait_seconds(failures, limit, now, window):
    """Seconds until fewer than `limit` of these failures are still inside the window (0 = not blocked)."""
    times = list(failures.filter(at__gte=now - window).order_by("-at").values_list("at", flat=True)[:limit])
    if len(times) < limit:
        return 0
    return max(0, int((times[limit - 1] + window - now).total_seconds()) + 1)


def blocked_for(username, ip, now=None):
    """Seconds the sign-in is blocked for this username and address, or 0 when it is allowed."""
    now = now or timezone.now()
    window = timedelta(minutes=settings.HELPLY_LOGIN_LOCK_MINUTES)
    username = clean_username(username)
    waits = [_wait_seconds(LoginFailure.objects.filter(username=username, ip=ip), settings.HELPLY_LOGIN_MAX_FAILURES, now, window),
             _wait_seconds(LoginFailure.objects.filter(username=username), settings.HELPLY_LOGIN_MAX_FAILURES_USER, now, window)]
    if ip:
        waits.append(_wait_seconds(LoginFailure.objects.filter(ip=ip), settings.HELPLY_LOGIN_MAX_FAILURES_IP, now, window))
    return max(waits)


def record_failure(username, ip):
    username = clean_username(username)
    LoginFailure.objects.create(username=username, ip=ip)
    # housekeeping: nothing older than a day is ever looked at
    LoginFailure.objects.filter(at__lt=timezone.now() - timedelta(days=1)).delete()
    log.warning("Failed sign-in for %r from %s", username, ip or "unknown address")


def record_success(username, ip):
    LoginFailure.objects.filter(username=clean_username(username), ip=ip).delete()


def clean_email(value):
    return unicodedata.normalize("NFKC", value or "").strip().lower()[:254]


def reset_blocked(email, ip, now=None):
    """True when this reset request must not send an email (too many for this address or from this visitor)."""
    since = (now or timezone.now()) - timedelta(minutes=settings.HELPLY_RESET_WINDOW_MINUTES)
    email = clean_email(email)
    if ResetRequest.objects.filter(email=email, sent=True, at__gte=since).count() >= settings.HELPLY_RESET_MAX_PER_EMAIL:
        return True
    return bool(ip) and ResetRequest.objects.filter(ip=ip, at__gte=since).count() >= settings.HELPLY_RESET_MAX_PER_IP


def record_reset(email, ip, sent):
    ResetRequest.objects.create(email=clean_email(email), ip=ip, sent=sent)
    ResetRequest.objects.filter(at__lt=timezone.now() - timedelta(days=1)).delete()
    if not sent:
        log.warning("Password reset email suppressed for %r from %s (too many requests)", clean_email(email), ip or "unknown address")


def lock_message(seconds):
    minutes = max(1, -(-seconds // 60))
    return f"Too many failed sign-in attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
