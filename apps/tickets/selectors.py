from django.db.models import Q

from .models import Ticket


def visible_tickets(user):
    """Row-level scoping: who can see which tickets."""
    qs = Ticket.objects.select_related("requester", "assignee", "category")
    if user.is_administrator:
        return qs
    if user.is_technician:
        return qs.filter(
            Q(assignee=user) | Q(support_group__in=user.support_groups.all()) | Q(requester=user)
        ).distinct()
    return qs.filter(requester=user)
