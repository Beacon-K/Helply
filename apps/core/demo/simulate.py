"""Replay demo scenarios through the real workflow with a simulated clock."""
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from unittest import mock

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Department, User
from apps.assets.models import Asset
from apps.core.reference_data import SLA, ensure_categories
from apps.notifications.models import Notification
from apps.notifications.services import email_muted
from apps.sla import services as sla
from apps.sla.models import SLAPolicy
from apps.tickets import services, workflow
from apps.tickets.models import Category, Ticket

from . import people
from .tickets import SCENARIOS


@contextmanager
def clock(at):
    """Make timezone.now() - and therefore auto_now fields, SLA maths and audit events - return `at`."""
    with mock.patch("django.utils.timezone.now", return_value=at):
        yield


def ensure_organisation():
    """Create or update demo departments, users, support groups, SLA policies and assets."""
    depts = {name: Department.objects.get_or_create(name=name)[0] for name in {u[4] for u in people.USERS}}
    users = {}
    for username, first, last, role, dept, _title in people.USERS:
        user, created = User.objects.get_or_create(username=username)
        user.first_name, user.last_name, user.role = first, last, role
        user.department, user.email = depts[dept], f"{username}@example.com"
        if role == User.Role.SUPERVISOR:
            user.is_staff = user.is_superuser = True
        if created:
            user.set_password(people.DEMO_PASSWORD)
        user.save()
        users[username] = user

    groups, categories = ensure_categories()
    for name, members in people.GROUP_MEMBERS.items():
        groups[name].members.set([users[m] for m in members])

    for priority, name, response, resolution in SLA:
        SLAPolicy.objects.update_or_create(
            priority=priority, defaults={"name": name, "response_minutes": response, "resolution_minutes": resolution}
        )

    for tag, name, kind, status, owner, dept, serial, warranty in people.ASSETS:
        Asset.objects.update_or_create(asset_tag=tag, defaults={
            "name": name, "type": kind, "status": status, "owner": users.get(owner),
            "department": depts.get(dept) or Department.objects.get_or_create(name=dept)[0],
            "serial_number": serial, "warranty_expiry": warranty, "notes": people.ASSET_NOTES.get(tag, ""),
        })
    return users, categories


def _start_time(when, now):
    if when[0] == "ago":
        return now - timedelta(minutes=when[1])
    _, days_ago, hhmm = when
    local_now = timezone.localtime(now)
    d = local_now.date() - timedelta(days=days_ago)
    while d.weekday() >= 5:  # tickets are raised on working days
        d -= timedelta(days=1)
    hour, minute = map(int, hhmm.split(":"))
    return timezone.make_aware(datetime.combine(d, time(hour, minute)))


def build_timeline(now):
    """Every scenario step as (absolute time, order, scenario, step), sorted chronologically."""
    timeline, problems = [], []
    for order, scenario in enumerate(SCENARIOS):
        start = _start_time(scenario.when, now)
        timeline.append((start, order, -1, scenario, ("create",)))
        for i, (offset, *step) in enumerate(scenario.steps):
            at = start + timedelta(minutes=offset)
            if at >= now:
                problems.append(f"'{scenario.title}' step {step[0]} would happen in the future")
            timeline.append((at, order, i, scenario, tuple(step)))
    if problems:
        raise ValueError("Scenario timeline problems:\n  " + "\n  ".join(problems))
    return sorted(timeline, key=lambda item: item[:3])


def run(stdout=None):
    real_now = timezone.now()
    users, categories = ensure_organisation()
    assets = {a.asset_tag: a for a in Asset.objects.all()}
    supervisor = users["alice"]
    tickets, refs = {}, {}

    def who(ticket, name):
        return {"requester": ticket.requester, "assignee": ticket.assignee}.get(name) or users[name]

    def fmt(text):
        return text.format(**refs) if "{" in text else text

    with transaction.atomic(), email_muted():
        for at, order, _, scenario, step in build_timeline(real_now):
            with clock(at):
                sla.mark_breaches(now=at)
                if step[0] == "create":
                    ticket = services.create_ticket(
                        requester=users[scenario.requester], title=scenario.title, description=scenario.description,
                        impact=scenario.impact, urgency=scenario.urgency, channel=scenario.channel,
                        category=Category.objects.get(name=scenario.category) if scenario.category else None,
                        asset=assets.get(scenario.asset),
                    )
                    tickets[order] = ticket
                    if scenario.key:
                        refs[scenario.key] = ticket.reference
                    continue

                ticket = tickets[order]
                ticket.refresh_from_db()
                action, *args = step
                try:
                    _apply(ticket, action, args, who, fmt, users, categories, supervisor)
                except (workflow.TransitionError, ValueError, PermissionError) as e:
                    raise ValueError(f"'{scenario.title}': step {step} failed: {e}") from e

        sla.mark_breaches(now=real_now)
        # Older demo notifications count as already seen, so the bell shows only recent activity.
        Notification.objects.filter(created_at__lt=real_now - timedelta(days=1)).update(is_read=True)

    if stdout:
        stdout.write(f"Replayed {len(SCENARIOS)} tickets.")
    return list(tickets.values())


def _apply(ticket, action, args, who, fmt, users, categories, supervisor):
    if action == "assign":
        if ticket.assignee_id is None:  # keep the AI's choice if it already assigned someone
            workflow.assign(ticket, users[args[0]], actor=supervisor)
    elif action == "reassign":
        workflow.assign(ticket, users[args[0]], actor=supervisor)
    elif action == "category":
        workflow.recategorize(ticket, categories[args[0]], supervisor)
    elif action in ("start", "hold", "resume", "resolve"):
        workflow.perform(ticket, action, ticket.assignee, note=fmt(args[0]) if args else "")
    elif action == "reopen":
        workflow.perform(ticket, "reopen", ticket.requester, note=fmt(args[0]))
    elif action == "close":
        workflow.perform(ticket, "close", who(ticket, args[0]) if args else ticket.requester)
    elif action == "cancel":
        workflow.perform(ticket, "cancel", who(ticket, args[0]), note=fmt(args[1]))
    elif action in ("reply", "note"):
        services.add_comment(ticket, who(ticket, args[0]), fmt(args[1]), is_internal=(action == "note"))
    elif action == "survey":
        services.submit_survey(ticket, ticket.requester, args[0], args[1])
    else:
        raise ValueError(f"unknown action {action!r}")


def clear_tickets():
    """Delete all tickets (with comments, events, surveys, AI logs) and restart numbering at HLP-00001."""
    from django.core.management.color import no_style
    from django.db import connection

    from apps.ai.models import AISuggestion
    from apps.tickets.models import Satisfaction, TicketComment, TicketEvent

    deleted = Ticket.objects.all().delete()[0]
    Notification.objects.all().delete()
    tables = [m._meta.db_table for m in (Ticket, TicketComment, TicketEvent, Satisfaction, AISuggestion, Notification)]
    sql = connection.ops.sequence_reset_by_name_sql(no_style(), [{"table": t, "column": "id"} for t in tables])
    with connection.cursor() as cursor:
        for statement in sql:
            cursor.execute(statement)
    return deleted
