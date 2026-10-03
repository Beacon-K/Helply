"""Cloud servers (VPS) watched by the Helply agent, their metrics and alerts.

The agent on each server only *reports* numbers (CPU, memory, disk, network...). Helply never
sends commands back, so a stolen agent token can at worst submit fake numbers for one server.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

TOKEN_PREFIX = "hly_"


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Server(models.Model):
    class Provider(models.TextChoices):
        AWS = "aws", "Amazon Web Services"
        ORACLE = "oracle", "Oracle Cloud (OCI)"
        AZURE = "azure", "Microsoft Azure"
        GCP = "gcp", "Google Cloud"
        DIGITALOCEAN = "digitalocean", "DigitalOcean"
        HETZNER = "hetzner", "Hetzner"
        VULTR = "vultr", "Vultr"
        LINODE = "linode", "Akamai / Linode"
        OVH = "ovh", "OVHcloud"
        ALIBABA = "alibaba", "Alibaba Cloud"
        TENCENT = "tencent", "Tencent Cloud"
        RACKNERD = "racknerd", "RackNerd"
        OTHER = "other", "Other / on-premises"

    class Criticality(models.IntegerChoices):
        # Same scale as a ticket's impact, so an alert on this server raises a ticket with this impact.
        HIGH = 1, "High - business stops without it"
        MEDIUM = 2, "Medium - some people affected"
        LOW = 3, "Low - test or internal tools"

    # What IT records
    name = models.CharField(max_length=80, unique=True, help_text="Short name, e.g. web-prod-01")
    purpose = models.CharField(max_length=160, blank=True, help_text="What runs on it, e.g. Company website")
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.OTHER)
    region = models.CharField(max_length=60, blank=True, help_text="e.g. Toronto (tor1)")
    country_code = models.CharField(max_length=2, blank=True, help_text="ISO country code, e.g. CA")
    # True while Helply works the country out from the server's IP address; set to False when a person
    # picks one, so a later detection never overwrites it.
    country_auto = models.BooleanField(default=True, editable=False)
    public_ip = models.GenericIPAddressField(null=True, blank=True)
    plan = models.CharField(max_length=80, blank=True, help_text="e.g. 2 vCPU / 4 GB / 80 GB SSD")
    monthly_cost = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, help_text="CAD per month")
    expires_on = models.DateField(null=True, blank=True, help_text="Next renewal / billing end date")
    criticality = models.PositiveSmallIntegerField(choices=Criticality.choices, default=Criticality.MEDIUM)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="servers",
        limit_choices_to={"role__in": ["technician", "administrator"]}, help_text="Who looks after it",
    )
    notes = models.TextField(blank=True)
    asset = models.OneToOneField(
        "assets.Asset", null=True, blank=True, on_delete=models.SET_NULL, related_name="server",
        help_text="Matching entry in the asset register (created automatically)",
    )
    alerts_enabled = models.BooleanField(default=True)
    maintenance_until = models.DateTimeField(null=True, blank=True, help_text="Alerts are silenced until this time")

    # Agent credentials: only a hash is stored. The full token is shown once when it is created.
    token_lookup = models.CharField(max_length=16, unique=True, null=True, blank=True, editable=False)
    token_hash = models.CharField(max_length=64, blank=True, editable=False)
    token_created_at = models.DateTimeField(null=True, blank=True, editable=False)

    # Set while the server still has the placeholder name Helply gave it; the first report renames it
    # to the machine's hostname.
    auto_named = models.BooleanField(default=False, editable=False)

    # What the agent reports about the machine
    hostname = models.CharField(max_length=120, blank=True)
    vendor = models.CharField(max_length=160, blank=True, help_text="Hardware vendor / product the agent read")
    instance_type = models.CharField(max_length=80, blank=True, help_text="Cloud shape / size, e.g. VM.Standard.E2.1.Micro")
    os_family = models.CharField(max_length=20, blank=True)  # linux / windows
    os_name = models.CharField(max_length=120, blank=True)
    arch = models.CharField(max_length=20, blank=True)
    cpu_model = models.CharField(max_length=120, blank=True)
    cpu_cores = models.PositiveSmallIntegerField(null=True, blank=True)
    mem_total = models.BigIntegerField(null=True, blank=True)
    swap_total = models.BigIntegerField(null=True, blank=True)
    disk_total = models.BigIntegerField(null=True, blank=True)
    agent_version = models.CharField(max_length=20, blank=True)
    reported_ip = models.GenericIPAddressField(null=True, blank=True)

    # Latest reading (the history is in Metric / MetricHourly)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cpu = models.FloatField(null=True, blank=True)
    mem_used = models.BigIntegerField(null=True, blank=True)
    swap_used = models.BigIntegerField(null=True, blank=True)
    disk_used = models.BigIntegerField(null=True, blank=True)
    net_rx_rate = models.FloatField(null=True, blank=True)  # bytes per second
    net_tx_rate = models.FloatField(null=True, blank=True)
    net_rx_total = models.BigIntegerField(null=True, blank=True)  # bytes since boot
    net_tx_total = models.BigIntegerField(null=True, blank=True)
    load1 = models.FloatField(null=True, blank=True)
    load5 = models.FloatField(null=True, blank=True)
    load15 = models.FloatField(null=True, blank=True)
    processes = models.PositiveIntegerField(null=True, blank=True)
    uptime_seconds = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("monitoring:detail", args=[self.pk])

    # --- agent token -------------------------------------------------------------------------
    def issue_token(self):
        """Create a new agent token (replacing any old one) and return it. Only the hash is kept."""
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        self.token_lookup = token[len(TOKEN_PREFIX):len(TOKEN_PREFIX) + 12]
        self.token_hash = hash_token(token)
        self.token_created_at = timezone.now()
        return token

    @classmethod
    def for_token(cls, token):
        if not token or not token.startswith(TOKEN_PREFIX) or len(token) < len(TOKEN_PREFIX) + 20:
            return None
        server = cls.objects.filter(token_lookup=token[len(TOKEN_PREFIX):len(TOKEN_PREFIX) + 12]).first()
        if server and hmac.compare_digest(server.token_hash, hash_token(token)):
            return server
        return None

    # --- state ---------------------------------------------------------------------------------
    @property
    def in_maintenance(self):
        return bool(self.maintenance_until and self.maintenance_until > timezone.now())

    @property
    def is_online(self):
        return bool(self.last_seen_at and
                    timezone.now() - self.last_seen_at < timedelta(seconds=settings.HELPLY_MONITOR_OFFLINE_SECONDS))

    @property
    def status(self):
        """pending (never reported) / online / offline. Alerts are layered on top by the views."""
        if self.last_seen_at is None:
            return "pending"
        return "online" if self.is_online else "offline"

    @staticmethod
    def _pct(used, total):
        return round(used * 100 / total, 1) if used is not None and total else None

    @property
    def mem_percent(self):
        return self._pct(self.mem_used, self.mem_total)

    @property
    def swap_percent(self):
        return self._pct(self.swap_used, self.swap_total)

    @property
    def disk_percent(self):
        return self._pct(self.disk_used, self.disk_total)

    @property
    def country_name(self):
        from .countries import COUNTRIES
        return COUNTRIES.get(self.country_code, "")

    @property
    def flag_url(self):
        """URL of the flag image, or "" when the country is unknown (templates then show a globe)."""
        from django.templatetags.static import static
        return static(f"img/flags/{self.country_code.lower()}.svg") if self.country_name else ""

    @property
    def renewal_days_left(self):
        return (self.expires_on - timezone.localdate()).days if self.expires_on else None

    @property
    def os_icon(self):
        return "🪟" if self.os_family == "windows" else "🐧" if self.os_family == "linux" else "🖥️"


class Metric(models.Model):
    """One reading from the agent (about every 10 seconds). Kept for HELPLY_MONITOR_RAW_HOURS."""

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="metrics")
    at = models.DateTimeField()
    cpu = models.FloatField()
    mem = models.FloatField()  # percent
    swap = models.FloatField(null=True, blank=True)
    disk = models.FloatField()
    net_rx = models.FloatField()  # bytes per second
    net_tx = models.FloatField()
    load1 = models.FloatField(null=True, blank=True)
    processes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["at"]
        indexes = [models.Index(fields=["server", "at"])]


class MetricHourly(models.Model):
    """Hourly averages (and CPU peak) for the long-range charts. Kept for HELPLY_MONITOR_HOURLY_DAYS."""

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="hourly")
    hour = models.DateTimeField()
    cpu = models.FloatField()
    cpu_max = models.FloatField()
    mem = models.FloatField()
    disk = models.FloatField()
    net_rx = models.FloatField()
    net_tx = models.FloatField()
    load1 = models.FloatField(null=True, blank=True)
    samples = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["hour"]
        constraints = [models.UniqueConstraint(fields=["server", "hour"], name="one_rollup_per_server_hour")]


class Alert(models.Model):
    """A problem detected on a server. While it is open, a matching ticket tracks the work."""

    class Rule(models.TextChoices):
        OFFLINE = "offline", "Server offline"
        CPU = "cpu", "CPU overloaded"
        MEMORY = "memory", "Memory almost full"
        DISK = "disk", "Disk almost full"

    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="alerts")
    rule = models.CharField(max_length=20, choices=Rule.choices)
    started_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    value = models.FloatField(null=True, blank=True, help_text="Reading that triggered it")
    peak = models.FloatField(null=True, blank=True)
    message = models.CharField(max_length=240)
    ticket = models.ForeignKey("tickets.Ticket", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="monitor_alerts")

    class Meta:
        ordering = ["-started_at"]
        constraints = [models.UniqueConstraint(fields=["server", "rule"], condition=models.Q(resolved_at__isnull=True),
                                               name="one_open_alert_per_rule")]

    def __str__(self):
        return f"{self.server}: {self.get_rule_display()}"

    @property
    def is_open(self):
        return self.resolved_at is None

    @property
    def duration(self):
        return (self.resolved_at or timezone.now()) - self.started_at
