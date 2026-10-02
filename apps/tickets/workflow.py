"""Ticket lifecycle state machine.

    NEW -> TRIAGED -> ASSIGNED -> IN_PROGRESS <-> ON_HOLD
                                      |
                                  RESOLVED -> CLOSED
                                      '-> (reopen) IN_PROGRESS
    NEW / TRIAGED / ASSIGNED -> CANCELLED

Every allowed move, who may make it, and its side effects live here, so the
rules are testable and the views stay thin.
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.sla import services as sla

from .choices import OPEN_STATUSES, Status
from .models import TicketEvent

TECH, SUP = User.Role.TECHNICIAN, User.Role.SUPERVISOR


class TransitionError(Exception):
    pass


@dataclass(frozen=True)
class Transition:
    name: str
    label: str
    sources: frozenset
    target: str
    roles: frozenset = field(default_factory=frozenset)
    requester_allowed: bool = False  # the ticket's requester may perform it
    assignee_only: bool = False  # technicians may only act on their own tickets
    note_required: bool = False


TRANSITIONS = {
    t.name: t
    for t in [
        Transition("triage", "Mark triaged", frozenset({Status.NEW}), Status.TRIAGED, frozenset({SUP})),
        Transition("start", "Start work", frozenset({Status.ASSIGNED}), Status.IN_PROGRESS,
                   frozenset({TECH, SUP}), assignee_only=True),
        Transition("hold", "Put on hold", frozenset({Status.IN_PROGRESS}), Status.ON_HOLD,
                   frozenset({TECH, SUP}), assignee_only=True, note_required=True),
        Transition("resume", "Resume", frozenset({Status.ON_HOLD}), Status.IN_PROGRESS,
                   frozenset({TECH, SUP}), assignee_only=True),
        Transition("resolve", "Resolve", frozenset({Status.IN_PROGRESS}), Status.RESOLVED,
                   frozenset({TECH, SUP}), assignee_only=True, note_required=True),
        Transition("reopen", "Reopen", frozenset({Status.RESOLVED}), Status.IN_PROGRESS,
                   requester_allowed=True, note_required=True),
        Transition("close", "Confirm & close", frozenset({Status.RESOLVED}), Status.CLOSED,
                   frozenset({SUP}), requester_allowed=True),
        Transition("cancel", "Cancel", frozenset({Status.NEW, Status.TRIAGED, Status.ASSIGNED}),
                   Status.CANCELLED, frozenset({SUP}), requester_allowed=True),
    ]
}


def can_perform(transition, ticket, user):
    if ticket.status not in transition.sources:
        return False
    if transition.requester_allowed and ticket.requester_id == user.pk:
        return True
    if user.role not in transition.roles:
        return False
    if transition.assignee_only and user.role == TECH and ticket.assignee_id != user.pk:
        return False
    return True


def available_transitions(ticket, user):
    return [t for t in TRANSITIONS.values() if can_perform(t, ticket, user)]


def perform(ticket, name, user, note=""):
    transition = TRANSITIONS.get(name)
    if transition is None:
        raise TransitionError(f"Unknown action '{name}'.")
    if ticket.status not in transition.sources:
        raise TransitionError(f"Cannot {transition.label.lower()} a ticket that is {ticket.get_status_display().lower()}.")
    if not can_perform(transition, ticket, user):
        raise TransitionError("You are not allowed to perform this action.")
    note = note.strip()
    if transition.note_required and not note:
        raise TransitionError(f"A note is required to {transition.label.lower()}.")

    now = timezone.now()
    from_status = ticket.status
    with transaction.atomic():
        ticket.status = transition.target
        if name == "start" and ticket.first_response_at is None:
            ticket.first_response_at = now
        elif name == "hold":
            sla.pause(ticket, now)
        elif name == "resume":
            sla.resume(ticket, now)
        elif name == "resolve":
            ticket.resolved_at = now
            ticket.resolution_note = note
        elif name == "reopen":
            ticket.resolved_at = None
        elif name in ("close", "cancel"):
            ticket.closed_at = now
        ticket.save()
        if name == "close":
            _record_ai_feedback(ticket, confirmed_category=ticket.category)
        TicketEvent.objects.create(
            ticket=ticket, actor=user, kind=TicketEvent.Kind.TRANSITION,
            from_status=from_status, to_status=ticket.status, note=note,
        )
    return ticket


def assign(ticket, assignee, actor=None):
    """Assign (or reassign) a ticket. actor=None means the system/AI did it."""
    if actor is not None and not actor.is_supervisor:
        raise TransitionError("Only supervisors can assign tickets.")
    if ticket.status not in OPEN_STATUSES:
        raise TransitionError("Only open tickets can be assigned.")
    if not assignee.is_agent:
        raise TransitionError("Tickets can only be assigned to technicians or supervisors.")

    with transaction.atomic():
        from_status = ticket.status
        ticket.assignee = assignee
        if ticket.status in (Status.NEW, Status.TRIAGED):
            ticket.status = Status.ASSIGNED
        ticket.save()
        TicketEvent.objects.create(
            ticket=ticket, actor=actor, kind=TicketEvent.Kind.ASSIGNED,
            from_status=from_status, to_status=ticket.status, note=f"Assigned to {assignee}",
        )
    return ticket


def can_recategorize(ticket, user):
    return ticket.is_open and (user.is_supervisor or (user.is_technician and ticket.assignee_id == user.pk))


def recategorize(ticket, category, actor):
    """Change a ticket's category (e.g. correcting the AI) and route it to that category's group."""
    if not can_recategorize(ticket, actor):
        raise TransitionError("Only a supervisor or the assigned technician can change the category.")
    if ticket.category_id == category.pk:
        return ticket
    with transaction.atomic():
        old = ticket.category
        ticket.category = category
        ticket.ai_classified = False
        if category.default_group_id:
            ticket.support_group = category.default_group
        ticket.save()
        TicketEvent.objects.create(
            ticket=ticket, actor=actor, kind=TicketEvent.Kind.UPDATED,
            note=f"Category changed from '{old or 'none'}' to '{category}'",
        )
        _record_ai_feedback(ticket, confirmed_category=category)
    return ticket


def _record_ai_feedback(ticket, confirmed_category):
    """Mark the AI's category suggestion as right or wrong once a human has settled the category.

    This is what the dashboard's "AI accuracy" figure is computed from.
    """
    from apps.ai.models import AISuggestion

    suggestion = ticket.ai_suggestions.filter(kind=AISuggestion.Kind.CLASSIFY, accepted__isnull=True).first()
    if suggestion is None or confirmed_category is None or suggestion.payload.get("category_id") is None:
        return
    suggestion.accepted = suggestion.payload["category_id"] == confirmed_category.pk
    suggestion.save(update_fields=["accepted"])
