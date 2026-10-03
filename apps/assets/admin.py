from django.contrib import admin

from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "name", "type", "status", "owner", "location", "purchase_cost", "warranty_expiry")
    list_filter = ("type", "status", "department", "location")
    search_fields = ("asset_tag", "name", "serial_number", "location", "supplier", "notes")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("asset_tag", "name", "type", "status", "serial_number")}),
        ("Assignment", {"fields": ("owner", "department", "location")}),
        ("Purchase & warranty", {"fields": ("supplier", "purchase_date", "purchase_cost", "warranty_expiry")}),
        ("Notes", {"fields": ("notes", "created_at", "updated_at")}),
    )
