from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Asset(models.Model):
    """An item in the IT asset register (hardware, software licence, ...)."""

    class Type(models.TextChoices):
        LAPTOP = "laptop", _("Laptop")
        DESKTOP = "desktop", _("Desktop / workstation")
        MONITOR = "monitor", _("Monitor")
        PERIPHERAL = "peripheral", _("Peripheral / accessory")
        PHONE = "phone", _("Mobile phone")
        TABLET = "tablet", _("Tablet")
        PRINTER = "printer", _("Printer / scanner")
        SERVER = "server", _("Server")
        CLOUD = "cloud", _("Cloud server / VPS")
        STORAGE = "storage", _("Storage / NAS")
        NETWORK = "network", _("Network device")
        POWER = "power", _("Power / UPS")
        AV = "av", _("Meeting room / AV")
        LICENSE = "license", _("Software licence / subscription")
        OTHER = "other", _("Other")

    class Status(models.TextChoices):
        IN_USE = "in_use", _("In use")
        IN_STOCK = "in_stock", _("In stock")
        IN_REPAIR = "in_repair", _("In repair")
        RETIRED = "retired", _("Retired")

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

    # Line icons (24x24, stroke 1.6) so every device type reads in one set and takes the text colour.
    _ICON_PATHS = {
        "laptop": '<rect x="5" y="5" width="14" height="10" rx="1.5"/><path d="M3 19h18"/>',
        "desktop": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M8 20h8M12 16v4"/>',
        "monitor": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M8 20h8M12 16v4"/>',
        "peripheral": '<rect x="7" y="3" width="10" height="18" rx="5"/><path d="M12 3v6"/>',
        "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18.5h2"/>',
        "tablet": '<rect x="4.5" y="3" width="15" height="18" rx="2"/><path d="M11 18h2"/>',
        "printer": '<path d="M7 9V3h10v6"/><rect x="4" y="9" width="16" height="8" rx="1.5"/><path d="M7 14h10v7H7z"/>',
        "server": '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>',
        "cloud": '<path d="M7 18a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 9a4.5 4.5 0 0 1 .5 9Z"/>',
        "storage": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
        "network": '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 7v5M12 12l-6 5M12 12l6 5"/>',
        "power": '<rect x="3" y="8" width="16" height="8" rx="2"/><path d="M21 11v2"/>',
        "av": '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
        "license": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 7l3 3"/>',
        "other": '<path d="M12 3 3 7.5v9L12 21l9-4.5v-9Z"/><path d="m3 7.5 9 4.5 9-4.5M12 12v9"/>',
    }

    @classmethod
    def icon_for(cls, type_):
        from django.utils.html import format_html
        paths = cls._ICON_PATHS.get(type_, cls._ICON_PATHS["other"])
        return format_html('<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" '
                           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>', mark_safe(paths))

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"

    def get_absolute_url(self):
        return reverse("assets:detail", args=[self.pk])

    @property
    def icon(self):
        return self.icon_for(self.type)

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


class RenewalReminder(models.Model):
    """Records that a renewal reminder was sent, so each one goes out exactly once.

    Keyed on the renewal date as well: when the date moves (the subscription was renewed) the
    next cycle starts fresh and gets its own reminders.
    """

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="renewal_reminders")
    renewal_date = models.DateField()
    milestone = models.PositiveSmallIntegerField(help_text="Days before renewal this reminder was for (0 = due or overdue).")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["asset", "renewal_date", "milestone"], name="uniq_renewal_reminder")]
