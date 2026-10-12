from django.conf import settings
from django.db import models


class AISuggestion(models.Model):
    """Log of every AI output, plus whether a human accepted it.

    This is what lets the team measure AI accuracy (e.g. % of auto-triaged
    tickets whose category was later changed) instead of just claiming it.
    """

    class Kind(models.TextChoices):
        CLASSIFY = "classify", "Category classification"
        ASSIGN = "assign", "Assignee suggestion"
        SIMILAR = "similar", "Similar tickets"
        KB = "kb", "Knowledge base answer"
        COPILOT = "copilot", "Technician assistant"
        CHAT = "chat", "Assistant chat"
        SLA_RISK = "sla_risk", "SLA risk prediction"

    ticket = models.ForeignKey(
        "tickets.Ticket", null=True, blank=True, on_delete=models.CASCADE, related_name="ai_suggestions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_suggestions",
        help_text="Who asked, for assistant answers. Also drives the per-user rate limit.",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    backend = models.CharField(max_length=200)
    payload = models.JSONField(default=dict)
    confidence = models.FloatField(null=True, blank=True)
    applied = models.BooleanField(default=False, help_text="The system acted on this suggestion automatically.")
    accepted = models.BooleanField(null=True, blank=True, help_text="Human feedback: kept (True) or overridden (False).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "kind", "created_at"])]

class InsightReport(models.Model):
    """One run of the admin ticket analysis.

    `stats` holds the numbers counted by code (the only numbers the UI ever shows as facts);
    `analysis` holds the model's reading of them (causes, prevention), or null when no model
    was available. Keeping both lets the dashboard stay useful offline and keeps the AI's
    claims checkable against the counted data.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    period_days = models.PositiveSmallIntegerField(default=30)
    stats = models.JSONField(default=dict)
    analysis = models.JSONField(null=True, blank=True)
    backend = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
