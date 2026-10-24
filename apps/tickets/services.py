"""Use-case level operations on tickets (create, comment, survey)."""
from django.db import transaction
from django.utils import timezone

from apps.notifications import events
from apps.sla import services as sla

from .choices import Channel, Status
from .models import Satisfaction, Ticket, TicketComment, TicketEvent


def create_ticket(*, requester, title, description, impact, urgency,
                  category=None, asset=None, channel=Channel.PORTAL, created_by=None):
    """Submit a ticket: save it, let AI triage it if needed, start the SLA clock.

    `created_by` is the IT person who filed it for someone else (phone call, walk-up); the history records them.
    """
    from apps.ai import services as ai

    with transaction.atomic():
        ticket = Ticket.objects.create(
            requester=requester, title=title, description=description,
            impact=impact, urgency=urgency, category=category, asset=asset, channel=channel,
        )
        on_behalf = created_by is not None and created_by.pk != requester.pk
        TicketEvent.objects.create(ticket=ticket, actor=created_by if on_behalf else requester,
                                   kind=TicketEvent.Kind.CREATED, to_status=ticket.status,
                                   note=f"Submitted by {created_by} on behalf of {requester}" if on_behalf else "")
        if category is not None:
            ticket.support_group = category.default_group
        else:
            ai.auto_triage(ticket)
        sla.apply_policy(ticket)
        ticket.save()
        if ticket.status == Status.TRIAGED:
            ai.auto_assign(ticket)
        events.ticket_created(ticket)
    return ticket


def add_comment(ticket, author, body, is_internal=False):
    if is_internal and not author.is_agent:
        is_internal = False
    with transaction.atomic():
        comment = TicketComment.objects.create(ticket=ticket, author=author, body=body, is_internal=is_internal)
        # A public reply from an agent counts as first response for the SLA.
        if author.is_agent and not is_internal and ticket.first_response_at is None:
            ticket.first_response_at = timezone.now()
            ticket.save(update_fields=["first_response_at", "updated_at"])
        TicketEvent.objects.create(ticket=ticket, actor=author, kind=TicketEvent.Kind.COMMENT,
                                   note="Internal note" if is_internal else "Public reply")
        events.comment_added(comment)
    return comment


def submit_survey(ticket, user, rating, comment=""):
    if ticket.requester_id != user.pk:
        raise PermissionError("Only the requester can rate this ticket.")
    if ticket.status not in (Status.RESOLVED, Status.CLOSED):
        raise ValueError("Tickets can be rated once resolved.")
    return Satisfaction.objects.update_or_create(ticket=ticket, defaults={"rating": rating, "comment": comment})[0]
