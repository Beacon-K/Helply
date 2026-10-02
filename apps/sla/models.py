from django.db import models

from apps.tickets.choices import Priority


class SLAPolicy(models.Model):
    """Response / resolution targets per ticket priority."""

    priority = models.CharField(max_length=2, choices=Priority.choices, unique=True)
    name = models.CharField(max_length=100)
    response_minutes = models.PositiveIntegerField(help_text="Target time to first response.")
    resolution_minutes = models.PositiveIntegerField(help_text="Target time to resolution.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority"]
        verbose_name = "SLA policy"
        verbose_name_plural = "SLA policies"

    def __str__(self):
        return f"{self.priority} - {self.name}"
