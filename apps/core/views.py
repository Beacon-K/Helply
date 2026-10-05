"""Role-based dashboards: each role lands on the questions it cares about.

- Administrator: where are the problems, and how loaded is the team?
- Technician: what should I work on next?
- Employee:   where are my tickets, and can I fix it myself?
"""
from collections import Counter
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.ai.models import AISuggestion
from apps.kb.models import Article
from apps.sla.services import SLAState, sla_state
from apps.tickets.choices import LIST_FILTERS, OPEN_STATUSES, Status
from apps.tickets.models import Satisfaction, Ticket

from . import overview

# Most urgent first when sorting a queue.
URGENCY = {SLAState.BREACHED: 0, SLAState.AT_RISK: 1, SLAState.OK: 2, SLAState.NONE: 3, SLAState.PAUSED: 4}

# Employee-facing progress steps: (label, statuses that are "at" this step).
PROGRESS_STEPS = [
    ("Submitted", (Status.NEW, Status.TRIAGED)),
    ("Assigned", (Status.ASSIGNED,)),
    ("In progress", (Status.IN_PROGRESS, Status.ON_HOLD)),
    ("Resolved", (Status.RESOLVED, Status.CLOSED)),
]


@login_required
def dashboard(request):
    user, now = request.user, timezone.now()
    if user.is_administrator:
        context = administrator_context(user, now)
    elif user.is_technician:
        context = technician_context(user, now)
    else:
        context = employee_context(user)
    return render(request, "core/dashboard.html", context)


def administrator_context(user, now):
    open_tickets = list(Ticket.objects.filter(status__in=OPEN_STATUSES).select_related("assignee", "category"))
    state = {t.pk: sla_state(t, now) for t in open_tickets}
    breached = [t for t in open_tickets if state[t.pk] == SLAState.BREACHED or t.sla_breached]
    at_risk = [t for t in open_tickets if state[t.pk] == SLAState.AT_RISK]
    unassigned = [t for t in open_tickets if t.assignee_id is None]

    # One "needs attention" list, most serious reason first, each ticket once.
    attention, seen = [], set()
    for reason, group in (("breached", breached), ("at_risk", at_risk), ("unassigned", unassigned)):
        for t in sorted(group, key=lambda t: (t.priority, t.created_at)):
            if t.pk not in seen:
                seen.add(t.pk)
                attention.append((t, reason))

    # Where the open work sits (same groups as the ticket list filters).
    counts = Counter(Ticket.objects.exclude(status__in=[Status.CLOSED, Status.CANCELLED])
                     .values_list("status", flat=True))
    stages = [(key, LIST_FILTERS[key][0], sum(counts[s] for s in LIST_FILTERS[key][1]))
              for key in ("not_started", "in_progress", "on_hold", "resolved")]

    workload = []
    for tech in User.objects.filter(role=User.Role.TECHNICIAN, is_active=True).order_by("first_name"):
        theirs = [t for t in open_tickets if t.assignee_id == tech.pk]
        risky = sum(state[t.pk] in (SLAState.AT_RISK, SLAState.BREACHED) or t.sla_breached for t in theirs)
        workload.append((tech, len(theirs), risky))

    # Last 30 days of resolved work.
    since = now - timedelta(days=30)
    recent = Ticket.objects.filter(resolved_at__gte=since)
    met = sum(sla_state(t, now) == SLAState.MET for t in recent)
    total_recent = recent.count()
    csat = Satisfaction.objects.aggregate(avg=Avg("rating"))["avg"]
    reviewed = AISuggestion.objects.filter(kind=AISuggestion.Kind.CLASSIFY, accepted__isnull=False)

    return {
        "kpi": {
            "open": len(open_tickets),
            "not_started": sum(counts[s] for s in LIST_FILTERS["not_started"][1]),
            "on_hold": counts[Status.ON_HOLD],
            "breached": len(breached),
            "at_risk": len(at_risk),
            "sla_met_pct": round(100 * met / total_recent) if total_recent else None,
            "sla_met": met,
            "resolved_30d": total_recent,
            "csat": csat,
            "csat_n": Satisfaction.objects.count(),
            "ai_accuracy": ai_accuracy(),
            "ai_reviewed": reviewed.count(),
            "ai_auto": AISuggestion.objects.filter(kind=AISuggestion.Kind.CLASSIFY, applied=True).count(),
            "unassigned": len(unassigned),
        },
        "attention": attention[:8],
        "attention_more": max(0, len(attention) - 8),
        "stages": stages,
        "stage_max": max([n for *_, n in stages] + [1]),
        "workload": workload,
        "workload_max": max([n for _, n, _ in workload] + [len(unassigned), 1]),
        "unassigned": overview.unassigned_tickets(user),
        "servers": overview.server_health(),
        "people": overview.people_overview(),
        "renewals": overview.renewals_and_assets(),
    }


def technician_context(user, now):
    mine = list(Ticket.objects.filter(assignee=user, status__in=OPEN_STATUSES).select_related("requester", "category"))
    rows = [(t, sla_state(t, now)) for t in mine]
    far_future = now + timedelta(days=3650)
    rows.sort(key=lambda r: (URGENCY.get(r[1], 9), r[0].resolution_due_at or far_future))
    week = now - timedelta(days=7)
    my_csat = Satisfaction.objects.filter(ticket__assignee=user).aggregate(avg=Avg("rating"))["avg"]
    unassigned = overview.unassigned_tickets(user)
    return {
        "kpi": {
            "open": len(rows),
            "unassigned": unassigned["count"],
            "urgent": sum(s in (SLAState.AT_RISK, SLAState.BREACHED) for _, s in rows),
            "on_hold": sum(t.status == Status.ON_HOLD for t in mine),
            "resolved_7d": Ticket.objects.filter(assignee=user, resolved_at__gte=week).count(),
            "csat": my_csat,
        },
        "queue": rows,
        "awaiting": Ticket.objects.filter(assignee=user, status=Status.RESOLVED).select_related("requester"),
        "unassigned": unassigned,
        "servers": overview.server_health(),
        "renewals": overview.renewals_and_assets(),
    }


def employee_context(user):
    mine = Ticket.objects.filter(requester=user).select_related("assignee")
    open_rows = [(t, progress(t)) for t in mine.filter(status__in=OPEN_STATUSES)]
    return {
        "my_open": open_rows,
        "to_confirm": mine.filter(status=Status.RESOLVED),
        "recent_closed": mine.filter(status=Status.CLOSED).order_by("-closed_at")[:3],
        "popular": Article.objects.visible_to(user).order_by("-views", "title")[:5],
    }


def progress(ticket):
    """[(label, 'done' | 'current' | 'todo'), ...] for the employee progress bar."""
    current = next(i for i, (_, statuses) in enumerate(PROGRESS_STEPS) if ticket.status in statuses)
    steps = []
    for i, (label, _) in enumerate(PROGRESS_STEPS):
        if i == current and ticket.status == Status.ON_HOLD:
            label = "On hold"
        steps.append((label, "done" if i < current else "current" if i == current else "todo"))
    return steps


def ai_accuracy():
    """% of AI category suggestions that a human later confirmed (None until any are reviewed)."""
    reviewed = AISuggestion.objects.filter(kind=AISuggestion.Kind.CLASSIFY, accepted__isnull=False)
    total = reviewed.count()
    return round(100 * reviewed.filter(accepted=True).count() / total) if total else None
