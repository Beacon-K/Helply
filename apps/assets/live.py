"""Change detection for live-updating asset pages.

Pages poll a tiny "version" endpoint; the version changes whenever anything the
page shows changes (an asset is added, edited or removed, or a ticket about one
of the assets is raised or updated). Only then does the page fetch fresh content.
"""
import hashlib

from django.db.models import Count, Max

from apps.tickets.models import Ticket


def _version(*parts):
    raw = "|".join(str(p.timestamp()) if hasattr(p, "timestamp") else str(p) for p in parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def list_version(assets):
    a = assets.aggregate(n=Count("pk"), last=Max("updated_at"))
    t = Ticket.objects.filter(asset__in=assets.values("pk")).aggregate(n=Count("pk"), last=Max("updated_at"))
    return _version(a["n"], a["last"], t["n"], t["last"])


def detail_version(asset):
    t = asset.tickets.aggregate(n=Count("pk"), last=Max("updated_at"))
    return _version(asset.updated_at, asset.status, asset.owner_id, t["n"], t["last"])
