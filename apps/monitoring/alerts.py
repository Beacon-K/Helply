"""Alert rules. A problem opens an Alert and raises a ticket; recovery closes the alert and tells the
ticket's handler. Tickets are never closed automatically: a person confirms the cause and resolves it.

    offline  no report for HELPLY_MONITOR_ALERT_OFFLINE_SECONDS (checked by monitor_check)
    cpu      CPU >= HELPLY_MONITOR_CPU_PERCENT for HELPLY_MONITOR_SUSTAIN_MINUTES
    memory   memory >= HELPLY_MONITOR_MEM_PERCENT for HELPLY_MONITOR_SUSTAIN_MINUTES
    disk     disk >= HELPLY_MONITOR_DISK_PERCENT
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from .models import Alert, Metric, Server

log = logging.getLogger(__name__)

SYSTEM_USERNAME = "helply-monitor"
CATEGORY = "Servers & Cloud"
# Readings must drop this far below the threshold before an alert counts as recovered (stops flapping).
HYSTERESIS = {Alert.Rule.CPU: 10, Alert.Rule.MEMORY: 5, Alert.Rule.DISK: 3}

FIRST_STEPS = {
    Alert.Rule.OFFLINE: [
        "Check the provider's console: is the VM running, and is there a billing or abuse notice?",
        "Try to reach the public IP (ping / SSH / RDP) from outside the office network.",
        "If the VM is up, check whether the Helply agent service stopped (systemctl status helply-agent).",
    ],
    Alert.Rule.CPU: [
        "Find the busiest processes (top / Task Manager) and note what they are.",
        "Check for a traffic spike, a stuck backup or a runaway scheduled job.",
        "If the load is legitimate and recurring, consider a bigger plan.",
    ],
    Alert.Rule.MEMORY: [
        "Find the processes using the most memory and check for a leak (memory growing for days).",
        "Restart the affected service in a quiet period if it does not release memory.",
        "If usage is legitimate, consider more RAM or a swap file.",
    ],
    Alert.Rule.DISK: [
        "Find the largest folders (du -sh /* or WinDirStat).",
        "Look for old logs, backups or caches that can be rotated or moved to object storage.",
        "If the data is needed, resize the disk with the provider before it reaches 100%.",
    ],
}


def _fmt_pct(value):
    return f"{value:.0f}%" if value is not None else "?"


def evaluate_report(server, now, came_back=False):
    """Called for every report: recover 'offline', then check the resource rules."""
    if came_back or server.alerts.filter(rule=Alert.Rule.OFFLINE, resolved_at__isnull=True).exists():
        resolve(server, Alert.Rule.OFFLINE, now, "The server is reporting again.")

    sustain = timedelta(minutes=settings.HELPLY_MONITOR_SUSTAIN_MINUTES)
    _check_sustained(server, Alert.Rule.CPU, server.cpu, settings.HELPLY_MONITOR_CPU_PERCENT, "cpu", sustain, now)
    _check_sustained(server, Alert.Rule.MEMORY, server.mem_percent, settings.HELPLY_MONITOR_MEM_PERCENT, "mem",
                     sustain, now)

    disk, limit = server.disk_percent, settings.HELPLY_MONITOR_DISK_PERCENT
    if disk is not None and disk >= limit:
        free = (server.disk_total - server.disk_used) / 1024**3
        raise_alert(server, Alert.Rule.DISK, disk, now,
                    f"Disk {_fmt_pct(disk)} full on {server.name} ({free:.1f} GB free)")
    elif disk is not None and disk < limit - HYSTERESIS[Alert.Rule.DISK]:
        resolve(server, Alert.Rule.DISK, now, f"Disk usage is back to {_fmt_pct(disk)}.")


def _check_sustained(server, rule, value, limit, column, sustain, now):
    if value is None:
        return
    if value >= limit:
        window = Metric.objects.filter(server=server, at__gte=now - sustain, at__lte=now)
        stats = window.aggregate(low=Min(column), first=Min("at"))
        # Only alert when readings cover (almost) the whole window and none of them dipped below the limit.
        covered = stats["first"] is not None and stats["first"] <= now - sustain + timedelta(seconds=60)
        if covered and stats["low"] >= limit:
            minutes = settings.HELPLY_MONITOR_SUSTAIN_MINUTES
            label = "CPU" if rule == Alert.Rule.CPU else "Memory"
            raise_alert(server, rule, value, now, f"{label} at {_fmt_pct(value)} for {minutes}+ minutes on {server.name}")
    elif value < limit - HYSTERESIS[rule]:
        resolve(server, rule, now, f"Back to {_fmt_pct(value)}.")


def check_offline(now=None):
    """Raise 'offline' alerts for servers that stopped reporting. Run every 30-60 seconds."""
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=settings.HELPLY_MONITOR_ALERT_OFFLINE_SECONDS)
    raised = 0
    already = Alert.objects.filter(rule=Alert.Rule.OFFLINE, resolved_at__isnull=True).values("server_id")
    for server in Server.objects.filter(last_seen_at__lt=cutoff).exclude(pk__in=already):
        raise_alert(server, Alert.Rule.OFFLINE, None, now,
                    f"{server.name} is offline - no report since {timezone.localtime(server.last_seen_at):%H:%M}")
        raised += 1
    return raised


def raise_alert(server, rule, value, now, message):
    """Open an alert (once) and raise a ticket for it, unless alerts are paused for this server."""
    with transaction.atomic():
        alert = server.alerts.select_for_update().filter(rule=rule, resolved_at__isnull=True).first()
        if alert:
            if value is not None and (alert.peak is None or value > alert.peak):
                alert.peak = value
                alert.save(update_fields=["peak"])
            return alert
        alert = Alert.objects.create(server=server, rule=rule, started_at=now, value=value, peak=value, message=message)
        if server.alerts_enabled and not server.in_maintenance:
            try:
                alert.ticket = _ticket_for(alert)
                alert.save(update_fields=["ticket"])
            except Exception:  # monitoring must keep running even if ticket creation fails
                log.exception("Could not raise a ticket for alert %s", alert.pk)
    return alert


def resolve(server, rule, now, note):
    alert = server.alerts.filter(rule=rule, resolved_at__isnull=True).first()
    if alert is None:
        return None
    alert.resolved_at = now
    alert.save(update_fields=["resolved_at"])
    ticket = alert.ticket
    if ticket and ticket.is_open:
        from apps.notifications import events
        from apps.notifications.models import Notification
        from apps.notifications.services import notify
        from apps.tickets.models import TicketEvent

        took = _duration(alert.duration)
        TicketEvent.objects.create(ticket=ticket, kind=TicketEvent.Kind.MONITOR,
                                   note=f"Recovered after {took}. {note} Please confirm the cause and resolve the ticket.")
        notify(events._handler(ticket), Notification.Kind.MONITOR, f"{server.name} recovered ({alert.get_rule_display()})",
               ticket=ticket, body=f"Recovered after {took}. {note} Resolve the ticket once you know the cause.")
    return alert


def _duration(delta):
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours < 48 else f"{hours // 24} days"


def system_user():
    """The account that 'requests' monitoring tickets. It cannot log in."""
    from apps.accounts.models import User

    user, created = User.objects.get_or_create(username=SYSTEM_USERNAME, defaults={
        "first_name": "Helply", "last_name": "Monitor", "is_active": False, "role": User.Role.EMPLOYEE,
    })
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _ticket_for(alert):
    """Reuse the ticket if the same problem came back before anyone resolved it, else open a new one."""
    from apps.tickets.models import TicketEvent

    previous = (Alert.objects.filter(server=alert.server, rule=alert.rule, ticket__isnull=False)
                .exclude(pk=alert.pk).select_related("ticket").first())
    if previous and previous.ticket.is_open:
        TicketEvent.objects.create(ticket=previous.ticket, kind=TicketEvent.Kind.MONITOR,
                                   note=f"The problem came back: {alert.message}.")
        return previous.ticket
    return _create_ticket(alert)


def _create_ticket(alert):
    from apps.ai import services as ai
    from apps.core.reference_data import ensure_categories
    from apps.notifications import events
    from apps.notifications.models import Notification
    from apps.notifications.services import notify
    from apps.sla import services as sla
    from apps.tickets import workflow
    from apps.tickets.choices import Channel, Level, Status
    from apps.tickets.models import Ticket, TicketEvent

    server = alert.server
    _, categories = ensure_categories()
    category = categories[CATEGORY]
    urgent = alert.rule == Alert.Rule.OFFLINE or (alert.rule == Alert.Rule.DISK and (alert.value or 0) >= 95)
    requester = system_user()

    ticket = Ticket.objects.create(
        title=alert.message[:200], description=_description(alert), requester=requester,
        category=category, support_group=category.default_group, asset=server.asset, channel=Channel.MONITORING,
        impact=server.criticality, urgency=Level.HIGH if urgent else Level.MEDIUM, status=Status.TRIAGED,
    )
    TicketEvent.objects.create(ticket=ticket, kind=TicketEvent.Kind.CREATED, to_status=Status.NEW)
    TicketEvent.objects.create(ticket=ticket, kind=TicketEvent.Kind.MONITOR, from_status=Status.NEW,
                               to_status=Status.TRIAGED,
                               note=f"Raised automatically by Helply Monitor ({alert.get_rule_display().lower()}).")
    sla.apply_policy(ticket)
    ticket.save()

    owner = server.owner
    if owner and owner.is_active and owner.is_agent:
        workflow.assign(ticket, owner, actor=None)
    else:
        ai.auto_assign(ticket)
    ticket.refresh_from_db()
    if ticket.assignee_id is None:
        notify(events._administrators(), Notification.Kind.MONITOR, f"Server alert needs an owner: {server.name}",
               ticket=ticket, body=alert.message, email=True)
    elif alert.rule == Alert.Rule.OFFLINE and server.criticality == Server.Criticality.HIGH:
        notify(events._administrators(), Notification.Kind.MONITOR, f"Critical server offline: {server.name}",
               ticket=ticket, body=alert.message)
    return ticket


def _description(alert):
    s = alert.server
    lines = [f"Helply Monitor detected a problem: {alert.message}.", "",
             f"Server: {s.name}" + (f" - {s.purpose}" if s.purpose else ""),
             f"Provider: {s.get_provider_display()}" + (f", {s.region}" if s.region else ""),
             f"Address: {s.public_ip or s.reported_ip or 'unknown'}",
             f"System: {s.os_name or s.os_family or 'unknown'}"]
    if s.last_seen_at:
        lines.append(f"Last report: {timezone.localtime(s.last_seen_at):%b %d, %H:%M:%S}")
    if alert.rule != Alert.Rule.OFFLINE:
        lines.append(f"Readings: CPU {_fmt_pct(s.cpu)}, memory {_fmt_pct(s.mem_percent)}, disk {_fmt_pct(s.disk_percent)}")
    lines += ["", "Suggested first steps:"] + [f"{i}. {step}" for i, step in enumerate(FIRST_STEPS[alert.rule], 1)]
    lines += ["", "Helply adds a note to this ticket when the server recovers. Resolve it once the cause is known."]
    return "\n".join(lines)
