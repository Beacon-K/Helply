"""Receiving agent reports, and keeping the metric history small."""
import ipaddress
import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, Max
from django.db.models.functions import TruncHour
from django.utils import timezone

from . import alerts, geo
from .models import Metric, MetricHourly, Server

AGENT_VERSION_MAX = 20


class InvalidReport(ValueError):
    pass


def _number(value, low=0.0, high=float("inf")):
    """A finite number clamped to [low, high], or None. Reports come from outside, so trust nothing."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return min(max(number, low), high)


def _integer(value, high=2**62):
    number = _number(value, 0, high)
    return int(number) if number is not None else None


def _text(value, length):
    return str(value).strip()[:length] if isinstance(value, (str, int, float)) else ""


def _pair(block):
    block = block if isinstance(block, dict) else {}
    used, total = _integer(block.get("used")), _integer(block.get("total"))
    if used is not None and total:
        used = min(used, total)
    return used, total


def _percent(used, total):
    return used * 100 / total if used is not None and total else 0.0


def ingest(server, report, remote_ip=None, now=None):
    """Store one report from the agent. Returns False when it was ignored as too frequent."""
    if not isinstance(report, dict):
        raise InvalidReport("The report must be a JSON object.")
    now = now or timezone.now()
    if server.last_seen_at and (now - server.last_seen_at).total_seconds() < settings.HELPLY_MONITOR_MIN_INTERVAL:
        return False

    cpu = _number(report.get("cpu"), 0, 100)
    mem_used, mem_total = _pair(report.get("mem"))
    if cpu is None or not mem_total:
        raise InvalidReport("The report needs at least 'cpu' and 'mem'.")
    swap_used, swap_total = _pair(report.get("swap"))
    disk_used, disk_total = _pair(report.get("disk"))
    net = report.get("net") if isinstance(report.get("net"), dict) else {}
    load = report.get("load") if isinstance(report.get("load"), (list, tuple)) else []
    load = [_number(x, 0, 10_000) for x in list(load)[:3]] + [None] * (3 - min(len(load), 3))
    host = report.get("host") if isinstance(report.get("host"), dict) else {}

    was_offline = server.last_seen_at is not None and not server.is_online
    server.last_seen_at = now
    server.cpu = cpu
    server.mem_used, server.mem_total = mem_used, mem_total
    server.swap_used, server.swap_total = swap_used, swap_total
    server.disk_used, server.disk_total = disk_used, disk_total
    server.net_rx_rate = _number(net.get("rx_rate")) or 0.0
    server.net_tx_rate = _number(net.get("tx_rate")) or 0.0
    server.net_rx_total = _integer(net.get("rx_total"))
    server.net_tx_total = _integer(net.get("tx_total"))
    server.load1, server.load5, server.load15 = load
    server.processes = _integer(report.get("processes"), 10_000_000)
    server.uptime_seconds = _integer(report.get("uptime"))
    server.agent_version = _text(report.get("version"), AGENT_VERSION_MAX)
    if host:
        server.hostname = _text(host.get("hostname"), 120)
        family = _text(host.get("os_family"), 20).lower()
        server.os_family = family if family in ("linux", "windows", "darwin", "freebsd") else "other"
        server.os_name = _text(host.get("os_name"), 120)
        server.arch = _text(host.get("arch"), 20)
        server.cpu_model = _text(host.get("cpu_model"), 120)
        server.cpu_cores = _integer(host.get("cpu_cores"), 4096)
        server.vendor = _text(host.get("vendor"), 160)
        server.instance_type = _text(host.get("instance_type"), 80)
    if remote_ip:
        server.reported_ip = remote_ip
    details_changed = _apply_detection(server, host, remote_ip) if host else False
    details_changed = _detect_country(server, remote_ip) or details_changed

    with transaction.atomic():
        server.save()
        Metric.objects.create(
            server=server, at=now, cpu=cpu, mem=_percent(mem_used, mem_total),
            swap=_percent(swap_used, swap_total) if swap_total else None, disk=_percent(disk_used, disk_total),
            net_rx=server.net_rx_rate, net_tx=server.net_tx_rate, load1=load[0], processes=server.processes,
        )
        alerts.evaluate_report(server, now, came_back=was_offline)
        if details_changed:
            sync_asset(server)
    return True


def _unique_name(wanted, server):
    base = "".join(c if c.isalnum() or c in "-_." else "-" for c in wanted.strip())[:72].strip("-.") or "server"
    name, n = base, 2
    while Server.objects.exclude(pk=server.pk).filter(name=name).exists():
        name, n = f"{base}-{n}", n + 1
    return name


def _gb(value):
    return f"{value / 1024**3:.0f} GB" if value and value >= 1024**3 * 2 else f"{(value or 0) / 1024**3:.1f} GB"


def _detect_country(server, remote_ip):
    """Set the country from the server's public IP unless a person chose one. True when it changed."""
    if not server.country_auto:
        return False
    ip = server.public_ip or remote_ip
    code = geo.country_for_ip(ip) if ip else ""
    if not code or code == server.country_code:  # unknown address: keep what we had
        return False
    server.country_code = code
    return True


def _apply_detection(server, host, remote_ip):
    """Fill in what the agent detected, without overwriting anything a person entered.

    Returns True when something visible in the asset register changed.
    """
    before = (server.name, server.provider, server.region, server.public_ip, server.plan)
    if server.auto_named and server.hostname:
        server.name = _unique_name(server.hostname, server)
        server.auto_named = False
    detected = _text(host.get("provider"), 20)
    if server.provider == Server.Provider.OTHER and detected in Server.Provider.values:
        server.provider = detected
    if not server.region:
        server.region = _text(host.get("region"), 60)
    if not server.public_ip and remote_ip:
        try:
            if ipaddress.ip_address(remote_ip).is_global:
                server.public_ip = remote_ip
        except ValueError:
            pass
    if not server.plan and server.cpu_cores and server.mem_total:
        size = f"{server.cpu_cores} vCPU / {_gb(server.mem_total)} RAM / {_gb(server.disk_total)} disk"
        server.plan = f"{server.instance_type} · {size}" if server.instance_type else size
    return before != (server.name, server.provider, server.region, server.public_ip, server.plan)


def rollup(now=None):
    """Average raw readings into hourly rows (for every hour that has data), then delete old data.

    Safe to run as often as you like: the current hour is recalculated until it is over.
    """
    now = now or timezone.now()
    raw_cutoff = now - timedelta(hours=settings.HELPLY_MONITOR_RAW_HOURS)
    hourly_cutoff = now - timedelta(days=settings.HELPLY_MONITOR_HOURLY_DAYS)
    last = MetricHourly.objects.aggregate(last=Max("hour"))["last"]
    since = last if last else raw_cutoff  # redo the last stored hour: it may have been incomplete
    rows = (Metric.objects.filter(at__gte=since).annotate(h=TruncHour("at")).values("server_id", "h")
            .annotate(a_cpu=Avg("cpu"), a_cpu_max=Max("cpu"), a_mem=Avg("mem"), a_disk=Avg("disk"),
                      a_rx=Avg("net_rx"), a_tx=Avg("net_tx"), a_load=Avg("load1"), samples=Count("id")))
    written = 0
    for row in rows:
        MetricHourly.objects.update_or_create(server_id=row["server_id"], hour=row["h"], defaults={
            "cpu": row["a_cpu"], "cpu_max": row["a_cpu_max"], "mem": row["a_mem"], "disk": row["a_disk"],
            "net_rx": row["a_rx"], "net_tx": row["a_tx"], "load1": row["a_load"], "samples": row["samples"],
        })
        written += 1
    deleted_raw = Metric.objects.filter(at__lt=raw_cutoff).delete()[0]
    deleted_hourly = MetricHourly.objects.filter(hour__lt=hourly_cutoff).delete()[0]
    return written, deleted_raw, deleted_hourly


def sync_asset(server):
    """Keep the server's entry in the asset register in step (cost per year, renewal date, location)."""
    from apps.accounts.models import Department
    from apps.assets.models import Asset

    asset = server.asset
    if asset is None:
        numbers = [int(t.split("-")[1]) for t in Asset.objects.filter(asset_tag__startswith="VPS-")
                   .values_list("asset_tag", flat=True) if t.split("-")[1].isdigit()]
        asset = Asset(asset_tag=f"VPS-{max(numbers, default=0) + 1:04d}", type=Asset.Type.CLOUD,
                      status=Asset.Status.IN_USE, department=Department.objects.filter(name="IT").first())
    asset.name = f"{server.name}" + (f" - {server.purpose}" if server.purpose else "")
    asset.name = asset.name[:Asset._meta.get_field("name").max_length]
    asset.location = " · ".join(x for x in [server.get_provider_display(), server.country_name, server.region] if x)[:100]
    asset.supplier = server.get_provider_display()[:100]
    asset.purchase_cost = server.monthly_cost * 12 if server.monthly_cost is not None else None
    asset.warranty_expiry = server.expires_on
    asset.notes = " · ".join(x for x in [server.plan, f"IP {server.public_ip}" if server.public_ip else ""] if x)
    asset.save()
    if server.asset_id != asset.pk:
        server.asset = asset
        server.save(update_fields=["asset", "updated_at"])
    return asset


def discard_abandoned(now=None, hours=24):
    """Remove servers someone started adding but never connected (placeholder name, no report)."""
    from apps.assets.models import Asset

    cutoff = (now or timezone.now()) - timedelta(hours=hours)
    stale = Server.objects.filter(auto_named=True, last_seen_at__isnull=True, created_at__lt=cutoff)
    asset_ids = list(stale.values_list("asset_id", flat=True))
    count = stale.count()
    stale.delete()
    Asset.objects.filter(pk__in=asset_ids).delete()
    return count
