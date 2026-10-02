"""Ticket enumerations and the ITIL impact x urgency priority matrix.

Kept outside models.py so other apps (e.g. sla) can import them without
creating model import cycles.
"""
from django.db import models


class Status(models.TextChoices):
    NEW = "new", "New"
    TRIAGED = "triaged", "Triaged"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In progress"
    ON_HOLD = "on_hold", "On hold"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"


OPEN_STATUSES = (Status.NEW, Status.TRIAGED, Status.ASSIGNED, Status.IN_PROGRESS, Status.ON_HOLD)


class Level(models.IntegerChoices):
    HIGH = 1, "High"
    MEDIUM = 2, "Medium"
    LOW = 3, "Low"


class Priority(models.TextChoices):
    P1 = "P1", "P1 - Critical"
    P2 = "P2", "P2 - High"
    P3 = "P3", "P3 - Medium"
    P4 = "P4", "P4 - Low"


class Channel(models.TextChoices):
    PORTAL = "portal", "Self-service portal"
    EMAIL = "email", "Email"
    PHONE = "phone", "Phone"


# ITIL-style matrix: rows = impact, columns = urgency (1 = high).
PRIORITY_MATRIX = {
    (1, 1): Priority.P1, (1, 2): Priority.P2, (1, 3): Priority.P3,
    (2, 1): Priority.P2, (2, 2): Priority.P3, (2, 3): Priority.P4,
    (3, 1): Priority.P3, (3, 2): Priority.P4, (3, 3): Priority.P4,
}


def compute_priority(impact, urgency):
    return PRIORITY_MATRIX[(int(impact), int(urgency))]


# Simplified views for the ticket list. The workflow keeps every status (they
# matter for accountability, SLA and reporting), but people browsing the list
# only need to know roughly where a ticket is. Order = order of the filter bar.
LIST_FILTERS = {
    "open": ("Open", OPEN_STATUSES),
    "not_started": ("Not started", (Status.NEW, Status.TRIAGED, Status.ASSIGNED)),
    "in_progress": ("In progress", (Status.IN_PROGRESS,)),
    "on_hold": ("On hold", (Status.ON_HOLD,)),
    "resolved": ("Resolved", (Status.RESOLVED,)),
    "closed": ("Closed", (Status.CLOSED, Status.CANCELLED)),
    "all": ("All", tuple(Status)),
}
DEFAULT_LIST_FILTER = "open"
