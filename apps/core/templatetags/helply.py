from django import template
from django.utils import timezone
from django.utils.formats import date_format

register = template.Library()


def _compact(seconds):
    minutes = int(abs(seconds) // 60)
    days, rem = divmod(minutes, 24 * 60)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    return f"{mins}m"


@register.filter
def due_in(value):
    """'in 1h 29m' or '3h 5m overdue' - short enough to scan in a queue."""
    if not value:
        return "–"
    seconds = (value - timezone.now()).total_seconds()
    return f"in {_compact(seconds)}" if seconds >= 0 else f"{_compact(seconds)} overdue"


@register.filter
def ago(value):
    if not value:
        return "–"
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds >= 7 * 24 * 3600:  # older than a week: a date is easier to read
        return "on " + date_format(timezone.localtime(value), "M j")
    return f"{_compact(seconds)} ago"


@register.filter
def percent_of(value, total):
    """Width percentage for a simple bar."""
    try:
        return round(100 * value / total) if total else 0
    except (TypeError, ZeroDivisionError):
        return 0
