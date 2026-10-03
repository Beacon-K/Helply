"""Who hears about what. Called from the ticket workflow and scheduled jobs.

Email is reserved for moments that need someone to act (a reply, a request to
confirm, an SLA problem); everything else is in-app only.
"""
from .models import Notification
from .services import notify

K = Notification.Kind


def _administrators():
    from apps.accounts.models import User

    return list(User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True))


def _handler(ticket):
    """Whoever is responsible for the ticket right now: its assignee, or the administrators."""
    return [ticket.assignee] if ticket.assignee_id else _administrators()


def ticket_created(ticket):
    notify([ticket.requester], K.RECEIVED, "We received your ticket", ticket=ticket, email=True,
           body="IT will review it shortly. You'll be notified when someone replies or the status changes.")
    if ticket.assignee_id is None:
        notify(_administrators(), K.NEEDS_TRIAGE, f"New {ticket.priority} ticket needs triage", ticket=ticket,
               actor=ticket.requester, body=ticket.title)


def ticket_assigned(ticket, actor):
    notify([ticket.assignee], K.ASSIGNED, f"{ticket.priority} ticket assigned to you", ticket=ticket,
           actor=actor, email=True, body=ticket.title)
    notify([ticket.requester], K.ASSIGNED, f"Your ticket was assigned to {ticket.assignee}", ticket=ticket,
           actor=actor)


def comment_added(comment):
    ticket, author = comment.ticket, comment.author
    if comment.is_internal:
        notify([ticket.assignee], K.NOTE, f"{author} added an internal note", ticket=ticket, actor=author,
               body=comment.body)
    elif author.pk == ticket.requester_id:
        notify(_handler(ticket), K.REPLY, f"{author} replied", ticket=ticket, actor=author, email=True,
               body=comment.body)
    else:
        notify([ticket.requester], K.REPLY, f"{author} replied to your ticket", ticket=ticket, actor=author,
               email=True, body=comment.body)


def status_changed(ticket, action, actor, note=""):
    requester = [ticket.requester]
    if action == "start":
        notify(requester, K.STATUS, f"{actor} started working on your ticket", ticket=ticket, actor=actor)
    elif action == "hold":
        notify(requester, K.STATUS, "Your ticket is on hold", ticket=ticket, actor=actor, email=True, body=note)
    elif action == "resume":
        notify(requester, K.STATUS, "Work on your ticket has resumed", ticket=ticket, actor=actor)
    elif action == "resolve":
        notify(requester, K.RESOLVED, "Your ticket is resolved - please confirm", ticket=ticket, actor=actor,
               email=True, body=f"Resolution: {note}\n\nIf it is fixed, please confirm and rate the service. "
                                "If not, you can reopen the ticket.")
    elif action == "reopen":
        notify(_handler(ticket), K.REOPENED, f"{actor} reopened the ticket", ticket=ticket, actor=actor,
               email=True, body=note)
    elif action == "close":
        notify([ticket.assignee, ticket.requester], K.STATUS, f"Ticket closed by {actor}", ticket=ticket, actor=actor)
    elif action == "cancel":
        notify([ticket.assignee, ticket.requester], K.STATUS, f"Ticket cancelled by {actor}", ticket=ticket,
               actor=actor, body=note)


def sla_at_risk(ticket):
    notify(_handler(ticket), K.SLA_RISK, f"{ticket.priority} ticket is close to its SLA deadline",
           ticket=ticket, email=True, body=ticket.title)


def sla_breached(ticket, reasons):
    notify(_handler(ticket) + _administrators(), K.SLA_BREACH, f"SLA breached: {', '.join(reasons)}",
           ticket=ticket, email=True, body=ticket.title)


def confirmation_reminder(ticket):
    notify([ticket.requester], K.REMINDER, "Reminder: please confirm your ticket is fixed", ticket=ticket,
           email=True, body="If we don't hear back, the ticket will be closed automatically.")


def auto_closed(ticket, days):
    notify([ticket.requester, ticket.assignee], K.STATUS,
           f"Ticket closed automatically after {days} days without confirmation", ticket=ticket)
