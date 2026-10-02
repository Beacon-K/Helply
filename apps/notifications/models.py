from django.conf import settings
from django.db import models


class Notification(models.Model):
    """An in-app notification for one person. Some are also sent by email."""

    class Kind(models.TextChoices):
        RECEIVED = "received", "Ticket received"
        NEEDS_TRIAGE = "needs_triage", "Needs triage"
        ASSIGNED = "assigned", "Assigned"
        REPLY = "reply", "New reply"
        NOTE = "note", "Internal note"
        STATUS = "status", "Status change"
        RESOLVED = "resolved", "Resolved - please confirm"
        REOPENED = "reopened", "Reopened"
        SLA_RISK = "sla_risk", "SLA at risk"
        SLA_BREACH = "sla_breach", "SLA breached"
        REMINDER = "reminder", "Reminder"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    ticket = models.ForeignKey(
        "tickets.Ticket", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.recipient}: {self.title}"
