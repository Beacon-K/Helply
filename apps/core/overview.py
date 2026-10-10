"""Company-wide summaries for the dashboard: tickets nobody owns, people, cloud servers and renewals.

Everything is read from live data. Nothing is invented: a company with no servers or no renewals gets
an empty state, never sample numbers.
"""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.monitoring.presenters import overview_queryset, state_of
from apps.tickets.choices import OPEN_STATUSES
from apps.tickets.models import Ticket
from apps.tickets.selectors import visible_tickets

RENEWAL_WINDOW_DAYS = 30
OVERDUE_GRACE_DAYS = 14  # same cut-off as the renewal reminders: older than this is stale data, not news
# Worst first, so the servers that need a person are at the top of the dashboard card.
SERVER_ORDER = {"critical": 0, "offline": 1, "warning": 2, "pending": 3, "healthy": 4}


def unassigned_tickets(user, limit=5):
    """Open tickets with no technician yet, most urgent (priority, then oldest) first.

    Limited to the tickets this person may open: a technician only sees their own support groups' tickets,
    so a count that included the rest would link to tickets they cannot see.
    """
    open_unassigned = visible_tickets(user).filter(status__in=OPEN_STATUSES, assignee__isnull=True)
    rows = list(open_unassigned.select_related("category").order_by("priority", "created_at")[:limit])
    count = open_unassigned.count()
    return {"count": count, "rows": rows, "more": max(0, count - len(rows))}


def server_health(limit=5):
    """State of the monitored fleet: counts, averages and the servers that most need attention."""
    servers = list(overview_queryset())
    items = []
    for server in servers:
        open_alerts = [a for a in server.alerts.all() if a.resolved_at is None]
        state = state_of(server, open_alerts)
        items.append({
            "server": server, "state": state, "alerts": len(open_alerts), "online": server.status == "online",
            "bucket": "critical" if open_alerts else state, "cpu": server.cpu, "mem": server.mem_percent,
            "disk": server.disk_percent,
        })
    items.sort(key=lambda i: (SERVER_ORDER[i["bucket"]], i["server"].name.lower()))
    counts = {s: sum(i["state"] == s for i in items) for s in ("healthy", "warning", "offline", "pending")}
    online = [i for i in items if i["online"] and i["cpu"] is not None]
    total = len(items)
    return {
        "total": total, "counts": counts,
        "segments": [(s, counts[s], round(100 * counts[s] / total, 1)) for s in ("healthy", "warning", "offline", "pending")
                     if counts[s]] if total else [],
        "alerts": sum(i["alerts"] for i in items),
        "avg_cpu": round(sum(i["cpu"] for i in online) / len(online), 1) if online else None,
        "monthly": float(sum((i["server"].monthly_cost or 0) for i in items)),
        "rows": items[:limit], "more": max(0, total - limit),
    }


def people_overview():
    """Head count by role and by department (active people only). Every department is listed, never a "+ N more".""" 
    active = User.objects.filter(is_active=True)
    roles = {r: active.filter(role=r).count() for r in User.Role.values}
    rows = list(active.values("department_id", "department__name").annotate(n=Count("pk")))
    depts = sorted(({"key": r["department_id"] or "none", "name": r["department__name"] or "No department", "n": r["n"]}
                    for r in rows), key=lambda d: (d["key"] == "none", -d["n"], d["name"].lower()))
    return {
        "total": sum(roles.values()), "roles": roles, "departments": depts, "dept_max": max([d["n"] for d in depts] + [1]),
        "dept_total": len(depts),
        "turned_off": User.objects.filter(is_active=False).count(),
    }


def renewals_and_assets(limit=5):
    """Subscriptions (software licences and cloud servers) renewing soon or overdue, plus the asset problems to know about."""
    today = timezone.localdate()
    subscriptions = Asset.objects.filter(type__in=(Asset.Type.LICENSE, Asset.Type.CLOUD), warranty_expiry__isnull=False,
                                         warranty_expiry__lte=today + timedelta(days=RENEWAL_WINDOW_DAYS),
                                         warranty_expiry__gte=today - timedelta(days=OVERDUE_GRACE_DAYS)
                                         ).exclude(status=Asset.Status.RETIRED).order_by("warranty_expiry")
    due = []
    for asset in subscriptions[:limit]:
        days = (asset.warranty_expiry - today).days
        due.append({"asset": asset, "days": days, "overdue": days < 0, "today": days == 0,
                    "text": "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}" if days > 0
                    else f"{-days} day{'s' if days != -1 else ''} overdue"})
    live = Asset.objects.exclude(status=Asset.Status.RETIRED)
    hardware = live.exclude(type__in=(Asset.Type.LICENSE, Asset.Type.CLOUD))
    return {
        "due": due, "due_count": subscriptions.count(), "due_more": max(0, subscriptions.count() - limit),
        "overdue_count": subscriptions.filter(warranty_expiry__lt=today).count(),
        "warranty_expired": hardware.filter(warranty_expiry__lt=today).count(),
        "in_repair": live.filter(status=Asset.Status.IN_REPAIR).count(),
        "assets_total": live.count(),
    }
