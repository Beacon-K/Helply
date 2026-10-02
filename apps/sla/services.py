"""SLA engine: due-date calculation, pause/resume, state and breach detection.

All functions take a Ticket instance and mutate it in memory; callers are
responsible for saving (so the SLA update lands in the same transaction as
the business change that triggered it).
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.tickets.choices import OPEN_STATUSES, Status

from .models import SLAPolicy


class SLAState:
    NONE = "none"
    OK = "ok"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    PAUSED = "paused"
    MET = "met"


def get_policy(priority):
    return SLAPolicy.objects.filter(priority=priority, is_active=True).first()


def apply_policy(ticket, start=None):
    """Set response/resolution due dates from the policy for the ticket's priority."""
    policy = get_policy(ticket.priority)
    if policy is None:
        ticket.response_due_at = ticket.resolution_due_at = None
        return None
    start = start or ticket.created_at or timezone.now()
    ticket.response_due_at = start + timedelta(minutes=policy.response_minutes)
    ticket.resolution_due_at = start + timedelta(minutes=policy.resolution_minutes)
    return policy


def pause(ticket, now=None):
    """Stop the SLA clock (e.g. waiting on the requester)."""
    if ticket.sla_paused_at is None:
        ticket.sla_paused_at = now or timezone.now()


def resume(ticket, now=None):
    """Restart the clock, pushing due dates out by the time spent paused."""
    if ticket.sla_paused_at is None:
        return
    paused_for = (now or timezone.now()) - ticket.sla_paused_at
    if ticket.resolution_due_at:
        ticket.resolution_due_at += paused_for
    if ticket.response_due_at and ticket.first_response_at is None:
        ticket.response_due_at += paused_for
    ticket.sla_paused_at = None


def sla_state(ticket, now=None):
    if ticket.resolution_due_at is None or ticket.status == Status.CANCELLED:
        return SLAState.NONE
    if ticket.status in (Status.RESOLVED, Status.CLOSED):
        met = ticket.resolved_at and ticket.resolved_at <= ticket.resolution_due_at
        return SLAState.MET if met else SLAState.BREACHED
    if ticket.sla_paused_at:
        return SLAState.PAUSED
    now = now or timezone.now()
    if now > ticket.resolution_due_at:
        return SLAState.BREACHED
    window = (ticket.resolution_due_at - ticket.created_at).total_seconds()
    elapsed = (now - ticket.created_at).total_seconds()
    if window > 0 and elapsed / window >= settings.HELPLY_SLA_AT_RISK_RATIO:
        return SLAState.AT_RISK
    return SLAState.OK


def find_at_risk(now=None):
    from apps.tickets.models import Ticket

    now = now or timezone.now()
    candidates = Ticket.objects.filter(
        status__in=OPEN_STATUSES, sla_paused_at__isnull=True, resolution_due_at__gte=now
    )
    return [t for t in candidates if sla_state(t, now) == SLAState.AT_RISK]


def mark_breaches(now=None):
    """Flag newly breached open tickets and write an audit event. Returns them."""
    from apps.notifications import events
    from apps.tickets.models import Ticket, TicketEvent

    now = now or timezone.now()
    breached = []
    candidates = Ticket.objects.filter(
        status__in=OPEN_STATUSES, sla_breached=False, sla_paused_at__isnull=True
    ).select_for_update()
    with transaction.atomic():
        for ticket in candidates:
            reasons = []
            if ticket.first_response_at is None and ticket.response_due_at and now > ticket.response_due_at:
                reasons.append("response target missed")
            if ticket.resolution_due_at and now > ticket.resolution_due_at:
                reasons.append("resolution target missed")
            if reasons:
                ticket.sla_breached = True
                ticket.save(update_fields=["sla_breached", "updated_at"])
                TicketEvent.objects.create(
                    ticket=ticket, kind=TicketEvent.Kind.SLA, note="SLA breached: " + ", ".join(reasons)
                )
                events.sla_breached(ticket, reasons)
                breached.append(ticket)
    return breached


def warn_at_risk(now=None):
    """Notify once per ticket when it becomes at risk of breaching. Returns the tickets warned."""
    from apps.notifications import events

    warned = []
    for ticket in find_at_risk(now):
        if not ticket.sla_risk_notified:
            ticket.sla_risk_notified = True
            ticket.save(update_fields=["sla_risk_notified", "updated_at"])
            events.sla_at_risk(ticket)
            warned.append(ticket)
    return warned
