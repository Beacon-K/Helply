from django.contrib import admin

from .models import Alert, Server


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "provider", "region", "os_name", "last_seen_at", "monthly_cost", "expires_on")
    list_filter = ("provider", "os_family", "criticality", "alerts_enabled")
    search_fields = ("name", "purpose", "region", "hostname", "public_ip")
    readonly_fields = ("token_created_at", "hostname", "os_family", "os_name", "arch", "cpu_model", "cpu_cores",
                       "mem_total", "disk_total", "agent_version", "reported_ip", "last_seen_at", "created_at",
                       "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "purpose", "provider", "region", "public_ip", "plan", "criticality", "owner")}),
        ("Cost & renewal", {"fields": ("monthly_cost", "expires_on", "asset")}),
        ("Alerts", {"fields": ("alerts_enabled", "maintenance_until")}),
        ("Reported by the agent", {"fields": ("hostname", "os_family", "os_name", "arch", "cpu_model", "cpu_cores",
                                              "mem_total", "disk_total", "agent_version", "reported_ip", "last_seen_at",
                                              "token_created_at")}),
        ("Notes", {"fields": ("notes", "created_at", "updated_at")}),
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("server", "rule", "started_at", "resolved_at", "peak", "ticket")
    list_filter = ("rule", "server")
    readonly_fields = ("server", "rule", "started_at", "resolved_at", "value", "peak", "message", "ticket")
