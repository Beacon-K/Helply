import ipaddress
import secrets
import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.assets.models import Asset

from . import presenters, services
from .forms import ServerForm
from .models import Server

AGENT_FILES = {"helply_agent.py", "install.sh", "install.ps1"}
MAX_REPORT_BYTES = 64 * 1024


def _require_agent(user):
    if not user.is_agent:
        raise PermissionDenied("Server monitoring is for the IT team.")


def _require_admin(user):
    if not user.is_administrator:
        raise PermissionDenied("Only administrators can change monitored servers.")


@login_required
def server_list(request):
    _require_agent(request.user)
    servers = list(presenters.overview_queryset())
    data = presenters.fleet(servers)
    by_id = {s.pk: s for s in servers}
    rows = [{"s": by_id[item["id"]], "d": item} for item in data["servers"]]
    return render(request, "monitoring/list.html", {
        "rows": rows, "fleet": data, "summary": data["summary"],
    })


@login_required
@never_cache
def fleet_data(request):
    """Live data for the list page (polled every few seconds)."""
    _require_agent(request.user)
    return JsonResponse(presenters.fleet(presenters.overview_queryset()))


def _range(request):
    key = request.GET.get("range", "24h")
    return key if key in presenters.RANGES else "24h"


@login_required
def server_detail(request, pk):
    _require_agent(request.user)
    server = get_object_or_404(presenters.overview_queryset(), pk=pk)
    range_key = _range(request)
    snap = presenters.snapshot(server)
    tickets = []
    if server.asset_id:
        tickets = list(server.asset.tickets.select_related("assignee").order_by("-created_at")[:6])
    payload = {"server": snap, "series": presenters.series(server, range_key)}
    return render(request, "monitoring/detail.html", {
        "s": server, "d": snap, "range_key": range_key, "ranges": list(presenters.RANGES),
        "open_alerts": [a for a in server.alerts.all() if a.resolved_at is None],
        "alerts": server.alerts.select_related("ticket")[:12], "tickets": tickets,
        "payload": payload,
        "thresholds": {"cpu": settings.HELPLY_MONITOR_CPU_PERCENT, "mem": settings.HELPLY_MONITOR_MEM_PERCENT,
                       "disk": settings.HELPLY_MONITOR_DISK_PERCENT, "minutes": settings.HELPLY_MONITOR_SUSTAIN_MINUTES,
                       "offline": settings.HELPLY_MONITOR_ALERT_OFFLINE_SECONDS // 60},
    })


@login_required
@never_cache
def server_data(request, pk):
    """Live data for the detail page: the latest snapshot, plus chart series unless ?latest=1."""
    _require_agent(request.user)
    server = get_object_or_404(presenters.overview_queryset(), pk=pk)
    data = {"server": presenters.snapshot(server)}
    if request.GET.get("latest") != "1":
        data["series"] = presenters.series(server, _range(request))
    return JsonResponse(data)


# --- administration ---------------------------------------------------------------------------

def _remember_token(request, server, token):
    """Keep the new token for one page view only: it is shown once and never stored in plain text."""
    request.session["monitor_new_token"] = {"pk": server.pk, "token": token}


@login_required
def server_create(request):
    """One click: create a placeholder server and go straight to the install command.

    Everything else (name, system, size, provider, region, IP) is filled in from the agent's first
    report. Cost, renewal and owner can be added afterwards.
    """
    _require_admin(request.user)
    if request.method != "POST":
        return render(request, "monitoring/new.html")
    server = Server(name=f"new-server-{secrets.token_hex(2)}", auto_named=True)
    while Server.objects.filter(name=server.name).exists():
        server.name = f"new-server-{secrets.token_hex(2)}"
    token = server.issue_token()
    server.save()
    services.sync_asset(server)
    _remember_token(request, server, token)
    return redirect("monitoring:install", pk=server.pk)


@login_required
def server_edit(request, pk):
    _require_admin(request.user)
    server = get_object_or_404(Server, pk=pk)
    form = ServerForm(request.POST or None, instance=server)
    if request.method == "POST" and form.is_valid():
        server = form.save()
        services.sync_asset(server)
        messages.success(request, "Server details saved.")
        return redirect(server)
    return render(request, "monitoring/form.html", {"form": form, "s": server})


@login_required
@never_cache
def server_install(request, pk):
    _require_admin(request.user)
    server = get_object_or_404(Server, pk=pk)
    pending = request.session.pop("monitor_new_token", None)
    token = pending["token"] if pending and pending.get("pk") == server.pk else None
    base = request.build_absolute_uri("/").rstrip("/")
    is_local = request.get_host().split(":")[0] in ("127.0.0.1", "localhost", "::1")
    return render(request, "monitoring/install.html", {
        "s": server, "d": presenters.snapshot(server), "token": token, "base": base, "is_local": is_local,
    })


@login_required
@require_POST
def server_token(request, pk):
    _require_admin(request.user)
    server = get_object_or_404(Server, pk=pk)
    token = server.issue_token()
    server.save(update_fields=["token_lookup", "token_hash", "token_created_at", "updated_at"])
    _remember_token(request, server, token)
    if server.last_seen_at:
        messages.warning(request, "A new agent token was created. The old one no longer works - update the agent now.")
    return redirect("monitoring:install", pk=server.pk)


@login_required
@require_POST
def server_maintenance(request, pk):
    _require_admin(request.user)
    server = get_object_or_404(Server, pk=pk)
    try:
        hours = max(0, min(int(request.POST.get("hours", "0")), 24 * 7))
    except ValueError:
        hours = 0
    server.maintenance_until = timezone.now() + timedelta(hours=hours) if hours else None
    server.save(update_fields=["maintenance_until", "updated_at"])
    if hours:
        messages.success(request, f"Alerts for {server.name} are paused for {hours} hour{'s' if hours != 1 else ''}.")
    else:
        messages.success(request, f"Maintenance mode ended for {server.name}.")
    return redirect(server)


@login_required
@require_POST
def server_delete(request, pk):
    _require_admin(request.user)
    server = get_object_or_404(Server, pk=pk)
    name = server.name
    never_connected = server.last_seen_at is None
    asset_id = server.asset_id
    server.delete()
    if never_connected:
        Asset.objects.filter(pk=asset_id).delete()  # nothing worth keeping: it never reported
        messages.success(request, f"{name} was discarded.")
    else:
        Asset.objects.filter(pk=asset_id).update(status=Asset.Status.RETIRED, updated_at=timezone.now())
        messages.success(request, f"{name} was removed from monitoring. Its asset record was kept and marked retired.")
    return redirect("monitoring:list")


# --- agent endpoints (no login: the agent authenticates with its token) ------------------------

def _client_ip(request):
    remote = request.META.get("REMOTE_ADDR", "")
    candidate = remote
    if remote in ("127.0.0.1", "::1"):  # behind the local Cloudflare tunnel
        candidate = request.headers.get("CF-Connecting-IP", remote)
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


@csrf_exempt
@require_POST
def ingest(request):
    header = request.headers.get("Authorization", "")
    token = header[7:].strip() if header.startswith("Bearer ") else ""
    server = Server.for_token(token)
    if server is None:
        return JsonResponse({"ok": False, "error": "Unknown or revoked agent token."}, status=401)
    if len(request.body) > MAX_REPORT_BYTES:
        return JsonResponse({"ok": False, "error": "Report too large."}, status=413)
    try:
        report = json.loads(request.body)
        stored = services.ingest(server, report, remote_ip=_client_ip(request))
    except (ValueError, services.InvalidReport) as error:
        return JsonResponse({"ok": False, "error": str(error)[:200]}, status=400)
    return JsonResponse({"ok": True, "stored": stored})


def agent_file(request, name):
    """The agent and its installers, so a server can download them from this Helply. No secrets inside."""
    if name not in AGENT_FILES:
        raise Http404
    path = settings.BASE_DIR / "agent" / name
    if not path.exists():
        raise Http404
    text = path.read_text(encoding="utf-8")
    if not name.endswith(".ps1"):
        text = text.replace("\r\n", "\n")  # a Windows checkout must not break bash/python on Linux
    response = HttpResponse(text, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="{name}"'
    return response
