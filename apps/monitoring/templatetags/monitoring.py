from django import template
from django.utils import timezone

from apps.monitoring.charts import human_rate

register = template.Library()


@register.filter
def bytes_h(value):
    """1610612736 -> '1.5 GB'."""
    if value is None:
        return "–"
    value = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024


@register.filter
def rate(value):
    return human_rate(value)


@register.filter
def uptime(seconds):
    if seconds is None:
        return "–"
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {rest // 60}m"


@register.filter
def since(moment):
    """Compact age: '8s', '5 min', '3 h', '2 days'."""
    if moment is None:
        return "never"
    seconds = int((timezone.now() - moment).total_seconds())
    if seconds < 60:
        return f"{max(seconds, 0)}s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 172800:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} days"


@register.filter
def level(value):
    """CSS level for a percentage gauge."""
    if value is None:
        return "none"
    return "hot" if value >= 85 else "warm" if value >= 70 else "ok"


@register.filter
def duration(delta):
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours < 48 else f"{hours // 24} days"
