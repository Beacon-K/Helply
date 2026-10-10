"""Keeping the sign-in record (accounts.LoginRecord) up to date.

Three events feed it:
  * user_logged_in   starts a record: time, address, country, browser, role
  * user_logged_out  closes it
  * every page load  (middleware) moves `last_seen_at` forward, at most every 15 seconds per session, which
                     is what gives a session its online time when the person never clicks Sign out

Recording must never get in the way of signing in or browsing, so every database error is logged and swallowed.
This module has no pages and no admin entries on purpose: the records are for local audits only.
"""
import logging
import threading
import time

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone

from . import throttle
from .models import LoginRecord

log = logging.getLogger(__name__)
TOUCH_EVERY_SECONDS = 15  # online time is accurate to about this many seconds
_touched = {}
_lock = threading.Lock()


def _session_key(request):
    session = getattr(request, "session", None)
    if session is None:
        return ""
    if session.session_key is None:
        session.save()  # a brand-new session has no key until it is saved
    return session.session_key or ""


def _update(key, **changes):
    """Change the open record of this session; save() keeps the local-time text and online_seconds in step."""
    record = LoginRecord.objects.filter(session_key=key, logged_out_at__isnull=True).first()
    if record is not None:
        for name, value in changes.items():
            setattr(record, name, value)
        record.save()


@receiver(user_logged_in)
def start_record(sender, request, user, **kwargs):
    if request is None:
        return
    try:
        from apps.monitoring import geo

        ip = throttle.client_ip(request)
        LoginRecord.objects.create(
            user=user, username=user.get_username(), role=user.role, ip=ip, country=geo.country_for_ip(ip) if ip else "",
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300], session_key=_session_key(request))
    except Exception:  # never block a sign-in because the record could not be written
        log.exception("Could not record the sign-in of %s", getattr(user, "pk", "?"))


@receiver(user_logged_out)
def end_record(sender, request, user, **kwargs):
    if request is None or user is None:
        return
    try:
        key = _session_key(request)
        if key:
            _update(key, logged_out_at=timezone.now())
            with _lock:
                _touched.pop(key, None)
    except Exception:
        log.exception("Could not close the sign-in record")


class LoginActivityMiddleware:
    """Moves last_seen_at forward while someone keeps using their session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        session = getattr(request, "session", None)
        if user is not None and user.is_authenticated and session is not None and session.session_key:
            self._touch(session.session_key)
        return self.get_response(request)

    @staticmethod
    def _touch(key):
        now = time.monotonic()
        with _lock:
            if now - _touched.get(key, -TOUCH_EVERY_SECONDS) < TOUCH_EVERY_SECONDS:
                return
            if len(_touched) > 5000:  # forget sessions that ended without a sign-out
                _touched.clear()
            _touched[key] = now
        try:
            _update(key, last_seen_at=timezone.now())
        except Exception:
            log.exception("Could not update the sign-in record")
