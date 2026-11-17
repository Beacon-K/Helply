from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import QueryDict
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.accounts.decorators import agent_required
from apps.sla.services import sla_state
from apps.tickets.choices import OPEN_STATUSES
from apps.tickets.selectors import visible_tickets

from . import bulk
from .forms import AssetForm
from .live import detail_version, list_version
from .models import Asset

PAGE_SIZE = 10
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


def filter_assets(assets, type_filter="", status_filter="", q=""):
    """The register's search/filter rules, shared by the list page and the Excel export."""
    shown = assets
    if type_filter:
        shown = [a for a in shown if a.type == type_filter]
    if status_filter == "warranty":
        shown = [a for a in shown if a.warranty_state in ("expired", "expiring") and a.status != Asset.Status.RETIRED]
    elif status_filter:
        shown = [a for a in shown if a.status == status_filter]
    if q:
        shown = [a for a in shown if matches_search(a, q)]
    return shown


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

    shown = filter_assets(everything, type_filter, status_filter, q)
    page = Paginator(shown, PAGE_SIZE).get_page(request.GET.get("page"))
    # the filters, kept on the Previous / Next links (everything except the page number itself)
    keep = QueryDict(mutable=True)
    for key in ("q", "status", "type"):
        if request.GET.get(key):
            keep[key] = request.GET[key]

    type_counts = {}
    for a in everything:
        type_counts[a.type] = type_counts.get(a.type, 0) + 1
    context = {
        "assets": page.object_list,
        "page": page,
        "pager_query": keep.urlencode(),
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
        "types": [(value, label, Asset.icon_for(value), type_counts[value])
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


# ---------------------------------------------------------------- bulk Excel export / import

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IMPORT_SESSION_KEY = "asset_import"


def _xlsx_response(content, filename):
    response = HttpResponse(content, content_type=XLSX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@agent_required
def asset_export(request):
    """All assets matching the list page's current search/filter, as one .xlsx."""
    assets = filter_assets(list(visible_assets(request.user)), request.GET.get("type", ""),
                           request.GET.get("status", ""), request.GET.get("q", "").strip().lower())
    return _xlsx_response(bulk.export_bytes(assets), f"helply-assets-{timezone.localdate().isoformat()}.xlsx")


@agent_required
def asset_import_template(request):
    return _xlsx_response(bulk.template_bytes(), "helply-assets-template.xlsx")


@agent_required
@require_POST
def asset_import(request):
    """Step 1: read and validate the upload, keep only the cleaned cell text in the session, show a preview."""
    upload = request.FILES.get("file")
    if upload is None:
        messages.error(request, "Choose an .xlsx file to import.")
        return redirect("assets:list")
    try:
        parsed = bulk.read_upload(upload)
    except bulk.SheetError as exc:
        messages.error(request, f"Import rejected: {exc}")
        return redirect("assets:list")
    request.session[IMPORT_SESSION_KEY] = {"rows": [[n, d, e] for n, d, e in parsed],
                                           "token": get_random_string(24)}
    return redirect("assets:import_preview")


def _pending_plan(request):
    pending = request.session.get(IMPORT_SESSION_KEY)
    if not pending:
        return None, None
    # Classified again on every request: the database may have changed since the file was uploaded.
    return pending, bulk.classify([(n, d, e) for n, d, e in pending["rows"]])


@agent_required
def asset_import_preview(request):
    pending, plan = _pending_plan(request)
    if plan is None:
        messages.info(request, "There is no import waiting. Upload a file first.")
        return redirect("assets:list")
    return render(request, "assets/import_preview.html", {
        "plan": plan, "token": pending["token"],
        "can_apply": bool(plan["create"] or plan["update"]),
    })


@agent_required
@require_POST
def asset_import_confirm(request):
    """Step 2: apply the valid rows in one transaction. Rows with errors are skipped, nothing is deleted."""
    pending, plan = _pending_plan(request)
    if plan is None or request.POST.get("token") != pending["token"]:
        messages.error(request, "That import has expired. Upload the file again.")
        return redirect("assets:list")
    del request.session[IMPORT_SESSION_KEY]
    created, updated = bulk.apply_plan(plan)
    skipped = len(plan["errors"])
    messages.success(request, f"Import done: {created} created, {updated} updated, "
                              f"{len(plan['unchanged'])} unchanged, {skipped} skipped because of errors.")
    return redirect("assets:list")


@agent_required
@require_POST
def asset_import_cancel(request):
    request.session.pop(IMPORT_SESSION_KEY, None)
    return redirect("assets:list")


# ---------------------------------------------------------------- create / edit / delete

@agent_required
def asset_create(request):
    form = AssetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        asset = form.save()
        messages.success(request, f"Added {asset.asset_tag}.")
        return redirect(asset.get_absolute_url())
    return render(request, "assets/form.html", {"form": form, "asset": None})


@agent_required
def asset_edit(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    form = AssetForm(request.POST or None, instance=asset)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {asset.asset_tag}.")
        return redirect(asset.get_absolute_url())
    return render(request, "assets/form.html", {
        "form": form, "asset": asset, "ticket_count": asset.tickets.count(),
        "can_delete": not hasattr(asset, "server")})


@agent_required
@require_POST
def asset_delete(request, pk):
    """Tickets keep their history (the link is just cleared). An asset created by a monitored server is
    removed together with that server instead, so it cannot be deleted here."""
    asset = get_object_or_404(Asset, pk=pk)
    if hasattr(asset, "server"):
        messages.error(request, f"{asset.asset_tag} belongs to a monitored cloud server. Remove the server instead.")
        return redirect("assets:edit", pk=asset.pk)
    tag = asset.asset_tag
    asset.delete()
    messages.success(request, f"Deleted {tag}.")
    return redirect("assets:list")
