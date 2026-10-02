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
        SLA_RISK = "sla_risk", "SLA risk prediction"

    ticket = models.ForeignKey(
        "tickets.Ticket", null=True, blank=True, on_delete=models.CASCADE, related_name="ai_suggestions"
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
