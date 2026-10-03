"""Turn servers and their metrics into plain data for the pages and their JSON live updates."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import Metric, MetricHourly, Server

RANGES = {"1h": 1, "24h": 24, "7d": 24 * 7, "30d": 24 * 30}
SPARK_MINUTES = 30
SPARK_POINTS = 45
HOT = 85  # a meter turns red from here (alert thresholds are a little higher)


def state_of(server, open_alerts):
    """healthy / warning / offline / pending - drives colours and the filters."""
    if server.status in ("offline", "pending"):
        return server.status
    hot = any(v is not None and v >= HOT for v in (server.cpu, server.mem_percent, server.disk_percent))
    return "warning" if open_alerts or hot else "healthy"


def _epoch(moment):
    return int(moment.timestamp() * 1000) if moment else None


def _round(value, digits=1):
    return round(value, digits) if value is not None else None


def snapshot(server, open_alerts=None, spark=None):
    if open_alerts is None:
        open_alerts = [a for a in server.alerts.all() if a.resolved_at is None]
    return {
        "id": server.pk,
        "name": server.name,
        "state": state_of(server, open_alerts),
        "status": server.status,
        "maintenance": server.in_maintenance,
        "last_seen": _epoch(server.last_seen_at),
        "cpu": _round(server.cpu),
        "mem": _round(server.mem_percent),
        "mem_used": server.mem_used, "mem_total": server.mem_total,
        "disk": _round(server.disk_percent),
        "disk_used": server.disk_used, "disk_total": server.disk_total,
        "swap": _round(server.swap_percent),
        "rx": _round(server.net_rx_rate, 0), "tx": _round(server.net_tx_rate, 0),
        "rx_total": server.net_rx_total, "tx_total": server.net_tx_total,
        "load": [_round(server.load1, 2), _round(server.load5, 2), _round(server.load15, 2)],
        "processes": server.processes,
        "uptime": server.uptime_seconds,
        "cores": server.cpu_cores,
        "info": {
            "name": server.name, "hostname": server.hostname, "os": server.os_name, "os_family": server.os_family,
            "arch": server.arch, "cpu_model": server.cpu_model, "cores": server.cpu_cores,
            "mem_total": server.mem_total, "disk_total": server.disk_total,
            "ip": server.public_ip or server.reported_ip, "provider": server.get_provider_display(),
            "provider_key": server.provider, "region": server.region, "instance_type": server.instance_type,
            "country": server.country_name, "country_code": server.country_code, "flag": server.flag_url,
            "agent": server.agent_version,
        },
        "alerts": [{"rule": a.rule, "label": a.get_rule_display(), "message": a.message,
                    "since": _epoch(a.started_at), "ticket": a.ticket.reference if a.ticket else None,
                    "ticket_url": a.ticket.get_absolute_url() if a.ticket else None} for a in open_alerts],
        "spark": spark if spark is not None else [],
    }


def sparklines(servers, now=None):
    """CPU over the last 30 minutes for each server, thinned to a few dozen points (one query)."""
    now = now or timezone.now()
    since = now - timedelta(minutes=SPARK_MINUTES)
    rows = Metric.objects.filter(server__in=servers, at__gte=since).values_list("server_id", "at", "cpu")
    by_server = {}
    for server_id, at, cpu in rows.order_by("server_id", "at"):
        by_server.setdefault(server_id, []).append((int((at - since).total_seconds()), cpu))
    result = {}
    span = SPARK_MINUTES * 60
    for server_id, points in by_server.items():
        buckets = [[] for _ in range(SPARK_POINTS)]
        for offset, cpu in points:
            buckets[min(offset * SPARK_POINTS // span, SPARK_POINTS - 1)].append(cpu)
        result[server_id] = [round(sum(b) / len(b), 1) if b else None for b in buckets]
    return result


def fleet(servers):
    """The list page's data: one snapshot per server plus fleet-wide numbers."""
    servers = list(servers)
    sparks = sparklines(servers)
    items = [snapshot(s, spark=sparks.get(s.pk, [])) for s in servers]
    today = timezone.localdate()
    online = [i for i in items if i["status"] == "online"]
    renewals = sorted((s for s in servers if s.expires_on and s.expires_on >= today - timedelta(days=30)),
                      key=lambda s: s.expires_on)
    next_renewal = renewals[0] if renewals else None
    counts = {state: sum(i["state"] == state for i in items) for state in ("healthy", "warning", "offline", "pending")}
    return {
        "servers": items,
        "summary": {
            "total": len(items),
            "online": len(online),
            "counts": counts,
            "alerts": sum(len(i["alerts"]) for i in items),
            "avg_cpu": _round(sum(i["cpu"] or 0 for i in online) / len(online)) if online else None,
            "monthly": float(sum((s.monthly_cost or Decimal(0)) for s in servers)),
            "next_renewal": {"name": next_renewal.name, "date": next_renewal.expires_on.isoformat(),
                             "days": next_renewal.renewal_days_left} if next_renewal else None,
        },
        # Changes when something structural changes (a server added, removed, or changing state):
        # the page then re-renders instead of just updating numbers.
        "signature": "|".join(f"{i['id']}:{i['state']}:{len(i['alerts'])}:{int(i['maintenance'])}" for i in items),
        "now": _epoch(timezone.now()),
    }


def series(server, range_key):
    """Chart data as parallel arrays (compact JSON). Raw readings up to 48 h, hourly averages beyond."""
    hours = RANGES.get(range_key, 24)
    now = timezone.now()
    since = now - timedelta(hours=hours)
    hourly = []
    if hours > settings.HELPLY_MONITOR_RAW_HOURS:
        hourly = list(MetricHourly.objects.filter(server=server, hour__gte=since)
                      .values_list("hour", "cpu", "mem", "disk", "net_rx", "net_tx", "load1", "cpu_max"))
    if len(hourly) >= 3:
        rows = [r[:7] for r in hourly]
        peak = [_round(r[7]) for r in hourly]
    else:
        # short ranges, or a server too new to have hourly averages yet: use the raw readings
        rows = list(Metric.objects.filter(server=server, at__gte=since)
                    .values_list("at", "cpu", "mem", "disk", "net_rx", "net_tx", "load1"))
        rows = _thin(rows, 400)
        peak = None
    columns = list(zip(*rows)) if rows else [[]] * 7
    data = {
        "range": range_key, "from": _epoch(since), "to": _epoch(now),
        "t": [_epoch(t) for t in columns[0]],
        "cpu": [_round(v) for v in columns[1]], "mem": [_round(v) for v in columns[2]],
        "disk": [_round(v) for v in columns[3]],
        "rx": [_round(v, 0) for v in columns[4]], "tx": [_round(v, 0) for v in columns[5]],
        "load": [_round(v, 2) for v in columns[6]],
    }
    if peak is not None:
        data["peak"] = peak
    return data


def _thin(rows, limit):
    """Average neighbouring readings so a chart never has to draw thousands of points."""
    if len(rows) <= limit:
        return rows
    size = -(-len(rows) // limit)
    thinned = []
    for i in range(0, len(rows), size):
        chunk = rows[i:i + size]
        values = []
        for column in range(1, len(chunk[0])):
            numbers = [r[column] for r in chunk if r[column] is not None]
            values.append(sum(numbers) / len(numbers) if numbers else None)
        thinned.append((chunk[-1][0], *values))
    return thinned


def overview_queryset():
    return Server.objects.select_related("owner", "asset").prefetch_related("alerts__ticket")
