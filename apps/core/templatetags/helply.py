from django import template
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

register = template.Library()


def _compact(seconds):
    minutes = int(abs(seconds) // 60)
    days, rem = divmod(minutes, 24 * 60)
    hours, mins = divmod(rem, 60)
    # d / h / m are the short unit letters; French uses j (jour) and h
    if days:
        return _("%(d)sd %(h)sh") % {"d": days, "h": hours} if hours else _("%(d)sd") % {"d": days}
    if hours:
        return _("%(h)sh %(m)sm") % {"h": hours, "m": mins} if mins else _("%(h)sh") % {"h": hours}
    return _("%(m)sm") % {"m": mins}


@register.filter
def due_in(value):
    """'in 1h 29m' or '3h 5m overdue' - short enough to scan in a queue."""
    if not value:
        return "–"
    seconds = (value - timezone.now()).total_seconds()
    return _("in %(t)s") % {"t": _compact(seconds)} if seconds >= 0 else _("%(t)s overdue") % {"t": _compact(seconds)}


@register.filter
def ago(value):
    if not value:
        return "–"
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return _("just now")
    if seconds >= 7 * 24 * 3600:  # older than a week: a date is easier to read
        return _("on %(date)s") % {"date": date_format(timezone.localtime(value), _("M j"))}
    return _("%(t)s ago") % {"t": _compact(seconds)}


@register.filter
def percent_of(value, total):
    """Width percentage for a simple bar."""
    try:
        return round(100 * value / total) if total else 0
    except (TypeError, ZeroDivisionError):
        return 0


@register.filter
def money(value):
    """Whole dollars with comma separators, e.g. 85090 -> 85,090 (independent of the locale)."""
    try:
        return f"{round(float(value)):,}"
    except (TypeError, ValueError):
        return "–"


@register.filter
def money2(value):
    """Dollars and cents with comma separators, e.g. 1234.5 -> 1,234.50."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "–"

@register.filter
def num(value):
    """Whole number with comma thousands, the same in every locale (the usage card is read at a glance)."""
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return ""


@register.filter
def sla_label(state):
    """Readable name for an SLA state ('at_risk' -> 'At risk'), translated."""
    return {
        "none": _("No SLA"), "ok": _("On track"), "at_risk": _("At risk"), "breached": _("Breached"),
        "paused": _("Paused"), "met": _("Met"),
    }.get(state, state)
