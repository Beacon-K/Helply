from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.sla.services import sla_state
from apps.tickets.choices import OPEN_STATUSES
from apps.tickets.selectors import visible_tickets

from .models import Asset

REPEAT_WINDOW_DAYS = 90
REPEAT_THRESHOLD = 3  # this many tickets within the window flags a device with recurring problems


def visible_assets(user):
    qs = Asset.objects.select_related("owner", "department")
    return qs if user.is_agent else qs.filter(owner=user)


def with_ticket_counts(qs):
    since = timezone.now() - timedelta(days=REPEAT_WINDOW_DAYS)
    return qs.annotate(
        open_tickets=Count("tickets", filter=Q(tickets__status__in=OPEN_STATUSES), distinct=True),
        recent_tickets=Count("tickets", filter=Q(tickets__created_at__gte=since), distinct=True),
    )


@login_required
def asset_list(request):
    assets = with_ticket_counts(visible_assets(request.user))
    if not request.user.is_agent:
        return render(request, "assets/my_devices.html", {"assets": assets})

    everything = list(assets)
    type_filter = request.GET.get("type", "")
    status_filter = request.GET.get("status", "")
    q = request.GET.get("q", "").strip().lower()

    shown = everything
    if type_filter:
        shown = [a for a in shown if a.type == type_filter]
    if status_filter == "warranty":
        shown = [a for a in shown if a.warranty_state in ("expired", "expiring")]
    elif status_filter:
        shown = [a for a in shown if a.status == status_filter]
    if q:
        def matches(a):
            owner = a.owner.get_full_name() if a.owner else ""
            return any(q in (v or "").lower() for v in (a.asset_tag, a.name, a.serial_number, owner, str(a.department or "")))
        shown = [a for a in shown if matches(a)]

    type_counts = {}
    for a in everything:
        type_counts[a.type] = type_counts.get(a.type, 0) + 1
    context = {
        "assets": shown,
        "total": len(everything),
        "kpi": {
            "in_use": sum(a.status == Asset.Status.IN_USE for a in everything),
            "in_stock": sum(a.status == Asset.Status.IN_STOCK for a in everything),
            "in_repair": sum(a.status == Asset.Status.IN_REPAIR for a in everything),
            "expired": sum(a.warranty_state == "expired" for a in everything),
            "expiring": sum(a.warranty_state == "expiring" for a in everything),
        },
        "types": [(value, label, Asset.ICONS.get(value, ""), type_counts[value])
                  for value, label in Asset.Type.choices if value in type_counts],
        "statuses": Asset.Status.choices,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "q": request.GET.get("q", ""),
        "repeat_window": REPEAT_WINDOW_DAYS,
        "repeat_threshold": REPEAT_THRESHOLD,
    }
    return render(request, "assets/list.html", context)


@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(with_ticket_counts(visible_assets(request.user)), pk=pk)
    tickets = visible_tickets(request.user).filter(asset=asset).select_related("assignee", "category")
    return render(request, "assets/detail.html", {
        "asset": asset,
        "tickets": [(t, sla_state(t)) for t in tickets],
        "repeat_window": REPEAT_WINDOW_DAYS,
        "repeat_threshold": REPEAT_THRESHOLD,
    })
