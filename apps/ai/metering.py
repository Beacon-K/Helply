"""How much of the daily Cloudflare Workers AI allowance has been used, and a warning before it runs out.

Every number here comes from Cloudflare, none is estimated:

1. Account analytics (preferred): Cloudflare's own GraphQL usage data for the whole account, which also
   counts anything else using the same account. It needs the API token to carry the "Account Analytics:
   Read" permission; without it Cloudflare answers "not authorized" and we fall back to...
2. Helply's own calls: each response carries `usage.neurons`, which is stored (AIUsage) when it arrives.
   This is exact for what Helply spent, but cannot see other users of the same account.

The page says which of the two it is showing. The daily allowance resets at 00:00 UTC.
"""
import json
import logging
import urllib.request
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import AIUsage, UsageAlert

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
CACHE_KEY = "helply.ai.account_usage"
CACHE_SECONDS = 300
FETCH_TIMEOUT = 4
WARN, CRITICAL = 0.7, 0.9
ALERTS = (("high", 0.8), ("full", 1.0))
KEEP_DAYS = 60

QUERY = """query($a: String!, $from: Time!, $week: Time!, $to: Time!) { viewer { accounts(filter: {accountTag: $a}) {
  today: aiInferenceAdaptiveGroups(filter: {datetime_geq: $from, datetime_leq: $to}, limit: 100) {
    count dimensions { modelId } sum { totalNeurons } }
  week: aiInferenceAdaptiveGroups(filter: {datetime_geq: $week, datetime_leq: $to}, limit: 1000) {
    dimensions { date } sum { totalNeurons } } } } }"""


def day_start(now=None):
    """00:00 UTC of the current allowance day, which is when Cloudflare resets it."""
    now = (now or timezone.now()).astimezone(dt_timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def daily_limit():
    return settings.HELPLY_CF_DAILY_NEURONS


def configured():
    return bool(settings.HELPLY_CF_ACCOUNT_ID and settings.HELPLY_CF_API_TOKEN)


def record(model, usage):
    """Store the usage block of one successful Cloudflare response."""
    if not isinstance(usage, dict):
        return
    try:
        neurons = float(usage["neurons"]) if usage.get("neurons") is not None else None
    except (TypeError, ValueError):
        neurons = None
    AIUsage.objects.create(
        model=str(model)[:120], neurons=neurons,
        prompt_tokens=int(usage.get("prompt_tokens") or 0), completion_tokens=int(usage.get("completion_tokens") or 0))
    check_alerts(local_only=True)


def local_usage(now=None):
    """What Helply itself spent today and over the last week, from the stored responses."""
    start = day_start(now)
    today = AIUsage.objects.filter(created_at__gte=start)
    totals = today.aggregate(used=Sum("neurons"), calls=Count("pk"), unknown=Count("pk", filter=Q(neurons__isnull=True)))
    models = [{"model": r["model"], "requests": r["n"], "neurons": r["used"] or 0}
              for r in today.values("model").annotate(n=Count("pk"), used=Sum("neurons")).order_by("-used")]
    week = (AIUsage.objects.filter(created_at__gte=start - timedelta(days=6))
            .annotate(day=TruncDate("created_at", tzinfo=dt_timezone.utc)).values("day").annotate(used=Sum("neurons")))
    return {"used": totals["used"] or 0.0, "calls": totals["calls"], "unknown": totals["unknown"], "models": models,
            "days": {r["day"]: r["used"] or 0.0 for r in week}}


def _fetch_account(now):
    if not configured():
        return None
    start = day_start(now)
    stamp = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    body = json.dumps({"query": QUERY, "variables": {
        "a": settings.HELPLY_CF_ACCOUNT_ID, "from": stamp(start), "week": stamp(start - timedelta(days=6)),
        "to": stamp(now.astimezone(dt_timezone.utc))}}).encode()
    request = urllib.request.Request(GRAPHQL_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {settings.HELPLY_CF_API_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:  # noqa: S310 - fixed https URL
            payload = json.load(response)
        if payload.get("errors"):  # "not authorized for that account": the token lacks Analytics: Read
            return None
        account = payload["data"]["viewer"]["accounts"][0]
        days = {}
        for g in account["week"]:
            day = datetime.strptime(g["dimensions"]["date"], "%Y-%m-%d").date()
            days[day] = days.get(day, 0.0) + (g["sum"]["totalNeurons"] or 0.0)
        models = [{"model": g["dimensions"]["modelId"], "requests": g["count"], "neurons": g["sum"]["totalNeurons"] or 0.0}
                  for g in sorted(account["today"], key=lambda g: -(g["sum"]["totalNeurons"] or 0))]
        return {"used": sum(m["neurons"] for m in models), "calls": sum(m["requests"] for m in models),
                "unknown": 0, "models": models, "days": days}
    except Exception as exc:  # noqa: BLE001 - analytics are a nice-to-have; fall back to our own record
        logger.info("Cloudflare analytics unavailable (%s)", type(exc).__name__)
        return None


def account_usage(now=None):
    """Account-wide usage, cached for a few minutes (failures too, so a missing permission costs one call)."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached or None
    result = _fetch_account(now or timezone.now())
    cache.set(CACHE_KEY, result or False, CACHE_SECONDS)
    return result


def level_for(used, limit):
    if not limit:
        return "ok"
    share = used / limit
    return "exhausted" if share >= 1 else "critical" if share >= CRITICAL else "warn" if share >= WARN else "ok"


def snapshot(now=None):
    now = now or timezone.now()
    local = local_usage(now)
    account = account_usage(now) if configured() else None
    source = account or local
    start, limit = day_start(now), daily_limit()
    used = source["used"]
    days = [{"day": (start - timedelta(days=i)).date(), "neurons": source["days"].get((start - timedelta(days=i)).date(), 0.0)}
            for i in range(6, -1, -1)]
    return {
        "configured": configured(), "source": "account" if account else "helply", "used": used, "limit": limit,
        "percent": min(100, round(100 * used / limit)) if limit else None,
        "remaining": max(0, limit - used) if limit else None,
        "level": level_for(used, limit), "resets_at": start + timedelta(days=1),
        "calls": source["calls"], "unknown": local["unknown"], "models": source["models"], "days": days,
        "days_max": max([d["neurons"] for d in days] + [1]), "helply_used": local["used"],
        "external": bool(settings.HELPLY_EXT_API_KEY),
    }


def check_alerts(now=None, local_only=False):
    """Tell the administrators once per day when 80% and 100% of the allowance are gone."""
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    from apps.notifications.services import notify

    limit = daily_limit()
    if not limit:
        return
    now = now or timezone.now()
    used = local_usage(now)["used"] if local_only else snapshot(now)["used"]
    for level, threshold in ALERTS:
        if used < threshold * limit:
            continue
        _, created = UsageAlert.objects.get_or_create(day=day_start(now).date(), level=level)
        if not created:
            continue
        reset = timezone.localtime(day_start(now) + timedelta(days=1)).strftime("%H:%M")
        title = "AI allowance used up for today" if level == "full" else "80% of today's AI allowance is used"
        body = (f"{used:,.0f} of {limit:,} Neurons used. "
                + ("Helply now answers with keyword matching instead of AI" if level == "full"
                   else "AI keeps working until the allowance is gone, then Helply falls back to keyword matching")
                + f" until it resets at {reset} local time.")
        notify(User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True), Notification.Kind.REMINDER, title,
               body=body, url="/")


def prune(now=None):
    AIUsage.objects.filter(created_at__lt=(now or timezone.now()) - timedelta(days=KEEP_DAYS)).delete()
    UsageAlert.objects.filter(day__lt=(now or timezone.now()).date() - timedelta(days=KEEP_DAYS)).delete()
