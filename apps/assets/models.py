from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Asset(models.Model):
    """An item in the IT asset register (hardware, software licence, ...)."""

    class Type(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        DESKTOP = "desktop", "Desktop"
        MONITOR = "monitor", "Monitor"
        PRINTER = "printer", "Printer"
        PHONE = "phone", "Mobile phone"
        NETWORK = "network", "Network device"
        LICENSE = "license", "Software licence"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        IN_USE = "in_use", "In use"
        IN_STOCK = "in_stock", "In stock"
        IN_REPAIR = "in_repair", "In repair"
        RETIRED = "retired", "Retired"

    asset_tag = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=Type.choices)
    serial_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_STOCK)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    department = models.ForeignKey(
        "accounts.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["asset_tag"]

    # Days before expiry at which a warranty is flagged as "expiring soon".
    WARRANTY_WARNING_DAYS = 90

    ICONS = {
        "laptop": "💻", "desktop": "🖥️", "monitor": "🖥️", "printer": "🖨️",
        "phone": "📱", "network": "📡", "license": "🔑", "other": "📦",
    }

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"

    def get_absolute_url(self):
        return reverse("assets:detail", args=[self.pk])

    @property
    def icon(self):
        return self.ICONS.get(self.type, "📦")

    @property
    def warranty_days_left(self):
        return (self.warranty_expiry - timezone.localdate()).days if self.warranty_expiry else None

    @property
    def warranty_state(self):
        """'none' | 'expired' | 'expiring' | 'ok'"""
        days = self.warranty_days_left
        if days is None:
            return "none"
        if days < 0:
            return "expired"
        return "expiring" if days <= self.WARRANTY_WARNING_DAYS else "ok"
