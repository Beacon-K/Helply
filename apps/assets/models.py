from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Asset(models.Model):
    """An item in the IT asset register (hardware, software licence, ...)."""

    class Type(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        DESKTOP = "desktop", "Desktop / workstation"
        MONITOR = "monitor", "Monitor"
        PERIPHERAL = "peripheral", "Peripheral / accessory"
        PHONE = "phone", "Mobile phone"
        TABLET = "tablet", "Tablet"
        PRINTER = "printer", "Printer / scanner"
        SERVER = "server", "Server"
        CLOUD = "cloud", "Cloud server / VPS"
        STORAGE = "storage", "Storage / NAS"
        NETWORK = "network", "Network device"
        POWER = "power", "Power / UPS"
        AV = "av", "Meeting room / AV"
        LICENSE = "license", "Software licence / subscription"
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
    location = models.CharField(max_length=100, blank=True, help_text='Where it is, e.g. "Server room" or "Remote".')
    supplier = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                        help_text="Purchase price (CAD). For subscriptions: cost per year.")
    warranty_expiry = models.DateField(null=True, blank=True,
                                       help_text="Warranty end, or renewal date for licences and subscriptions.")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, db_index=True)

    class Meta:
        ordering = ["asset_tag"]

    # Days before expiry at which a warranty is flagged as "expiring soon".
    WARRANTY_WARNING_DAYS = 90

    ICONS = {
        "laptop": "💻", "desktop": "🖥️", "monitor": "🖥️", "peripheral": "🖱️", "phone": "📱", "tablet": "📲",
        "printer": "🖨️", "server": "🗄️", "cloud": "☁️", "storage": "💾", "network": "📡", "power": "🔋", "av": "🎥",
        "license": "🔑", "other": "📦",
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

    @property
    def age_years(self):
        """Age in years (one decimal), or None if the purchase date is unknown."""
        if not self.purchase_date:
            return None
        return round((timezone.localdate() - self.purchase_date).days / 365.25, 1)

    @property
    def is_subscription(self):
        """Paid per period and renewed (software, cloud servers) rather than bought once."""
        return self.type in (self.Type.LICENSE, self.Type.CLOUD)
