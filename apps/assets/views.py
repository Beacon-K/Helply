from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.sla.services import sla_state
from apps.tickets.choices import OPEN_STATUSES
from apps.tickets.selectors import visible_tickets

from .live import detail_version, list_version
from .models import Asset

REPEAT_WINDOW_DAYS = 90
REPEAT_THRESHOLD = 3  # this many tickets within the window flags a device with recurring problems


def matches_search(asset, query):
    """Every word must appear somewhere: tag, name, serial, type, status, owner, department, location,
    supplier or notes."""
    owner = f"{asset.owner.get_full_name()} {asset.owner.username}" if asset.owner else "shared"
    haystack = " ".join([
        asset.asset_tag, asset.name, asset.serial_number, asset.get_type_display(), asset.type,
        asset.get_status_display(), owner, str(asset.department or ""), asset.location, asset.supplier, asset.notes,
    ]).lower()
    return all(word in haystack for word in query.lower().split())


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
    live_version = list_version(visible_assets(request.user))
    if not request.user.is_agent:
        return render(request, "assets/my_devices.html", {"assets": assets, "live_version": live_version})

    everything = list(assets)
    type_filter = request.GET.get("type", "")
    status_filter = request.GET.get("status", "")
    q = request.GET.get("q", "").strip().lower()

    shown = everything
    if type_filter:
        shown = [a for a in shown if a.type == type_filter]
    if status_filter == "warranty":
        shown = [a for a in shown if a.warranty_state in ("expired", "expiring") and a.status != Asset.Status.RETIRED]
    elif status_filter:
        shown = [a for a in shown if a.status == status_filter]
    if q:
        shown = [a for a in shown if matches_search(a, q)]

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
            # Retired assets no longer need warranty cover, so they are left out of these two.
            "expired": sum(a.warranty_state == "expired" and a.status != Asset.Status.RETIRED for a in everything),
            "expiring": sum(a.warranty_state == "expiring" and a.status != Asset.Status.RETIRED for a in everything),
            # Hardware is valued at purchase price; subscriptions are a yearly running cost.
            "hardware_value": sum(a.purchase_cost or 0 for a in everything
                                  if not a.is_subscription and a.status != Asset.Status.RETIRED),
            "subscriptions": sum(a.purchase_cost or 0 for a in everything
                                 if a.is_subscription and a.status != Asset.Status.RETIRED),
        },
        "types": [(value, label, Asset.ICONS.get(value, ""), type_counts[value])
                  for value, label in Asset.Type.choices if value in type_counts],
        "statuses": Asset.Status.choices,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "q": request.GET.get("q", ""),
        "repeat_window": REPEAT_WINDOW_DAYS,
        "repeat_threshold": REPEAT_THRESHOLD,
        "live_version": live_version,
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
        "live_version": detail_version(asset),
    })


@login_required
def asset_list_version(request):
    """Tiny response polled by the asset list: changes whenever anything on the page would change."""
    return JsonResponse({"version": list_version(visible_assets(request.user))})


@login_required
def asset_detail_version(request, pk):
    asset = get_object_or_404(visible_assets(request.user), pk=pk)
    return JsonResponse({"version": detail_version(asset)})
