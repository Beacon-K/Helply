from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from .choices import OPEN_STATUSES, Channel, Level, Priority, Status, compute_priority


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    default_group = models.ForeignKey(
        "accounts.SupportGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="categories",
        help_text="Group that receives tickets in this category.",
    )
    keywords = models.TextField(
        blank=True, help_text="Comma-separated keywords used by the baseline AI classifier."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class Ticket(models.Model):
    Status = Status

    title = models.CharField(max_length=200)
    description = models.TextField()
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_tickets"
    )
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets"
    )
    asset = models.ForeignKey(
        "assets.Asset", null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets"
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.PORTAL)

    impact = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.MEDIUM)
    urgency = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.MEDIUM)
    priority = models.CharField(max_length=2, choices=Priority.choices, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    support_group = models.ForeignKey(
        "accounts.SupportGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    ai_classified = models.BooleanField(default=False, help_text="Category was set by the AI classifier.")
    resolution_note = models.TextField(blank=True)

    # Lifecycle timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # SLA tracking (maintained by apps.sla.services)
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    sla_paused_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["resolution_due_at"]),
        ]

    def __str__(self):
        return f"{self.reference} {self.title}"

    def save(self, *args, **kwargs):
        self.priority = compute_priority(self.impact, self.urgency)
        super().save(*args, **kwargs)

    @property
    def reference(self):
        return f"HLP-{self.pk:05d}" if self.pk else "HLP-new"

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    def get_absolute_url(self):
        return reverse("tickets:detail", args=[self.pk])


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Internal notes are hidden from the requester.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class TicketEvent(models.Model):
    """Immutable audit trail of everything that happens to a ticket."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        TRANSITION = "transition", "Status change"
        ASSIGNED = "assigned", "Assigned"
        UPDATED = "updated", "Updated"
        COMMENT = "comment", "Comment"
        SLA = "sla", "SLA"
        AI = "ai", "AI action"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Empty when the action was taken by the system or AI.",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    from_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class Satisfaction(models.Model):
    """Post-resolution follow-up survey (回访)."""

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="satisfaction")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
