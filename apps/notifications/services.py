"""Create notifications and send the email copies.

Every notification appears in-app. An email is sent as well when the event
asks for it, the person has email notifications on, and they have not already
been sent the same kind of email about the same ticket within
HELPLY_EMAIL_THROTTLE_MINUTES. A burst of five replies produces one email, while
different events (received, then replied, then resolved) still each get one.
"""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notification

log = logging.getLogger(__name__)
_email_muted = ContextVar("helply_email_muted", default=False)


@contextmanager
def email_muted():
    """Suppress emails (in-app notifications are still created), e.g. while loading demo data."""
    token = _email_muted.set(True)
    try:
        yield
    finally:
        _email_muted.reset(token)


def notify(recipients, kind, title, *, body="", ticket=None, actor=None, email=False, url=""):
    """Notify each recipient once, never the person who caused the event."""
    created = []
    seen = set()
    for user in recipients:
        if user is None or user.pk in seen or not user.is_active or (actor is not None and user.pk == actor.pk):
            continue
        seen.add(user.pk)
        note = Notification.objects.create(
            recipient=user, ticket=ticket, kind=kind, title=title, body=body,
            url=ticket.get_absolute_url() if ticket else url,
        )
        if email and _should_email(note):
            note.emailed = True
            note.save(update_fields=["emailed"])
            transaction.on_commit(lambda n=note: _send_email(n))
        created.append(note)
    return created


def _should_email(note):
    user = note.recipient
    if _email_muted.get() or not user.email or not user.email_notifications:
        return False
    if note.ticket_id is None:
        return True
    window_start = timezone.now() - timedelta(minutes=settings.HELPLY_EMAIL_THROTTLE_MINUTES)
    return not Notification.objects.filter(
        recipient=user, ticket_id=note.ticket_id, kind=note.kind, emailed=True, created_at__gte=window_start
    ).exclude(pk=note.pk).exists()


def _send_email(note):
    ticket = note.ticket
    subject = f"[Helply {ticket.reference}] {note.title}" if ticket else f"[Helply] {note.title}"
    lines = [f"Hi {note.recipient.first_name or note.recipient.username},", "", note.title]
    if ticket:
        lines += ["", f"Ticket: {ticket.reference} - {ticket.title}", f"Status: {ticket.get_status_display()}"]
    if note.body:
        lines += ["", note.body]
    if note.url:
        lines += ["", f"Open in Helply: {settings.HELPLY_SITE_URL}{note.url}"]
    lines += ["", "--", "Helply IT Service Desk",
              "You can turn email notifications off on your Notifications page in Helply."]
    try:
        send_mail(subject, "\n".join(lines), None, [note.recipient.email])
    except Exception:  # an email outage must never break the ticket workflow
        log.exception("Could not send notification email %s", note.pk)


def unread_count(user):
    return Notification.objects.filter(recipient=user, is_read=False).count()
