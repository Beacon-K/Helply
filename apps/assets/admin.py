from django.contrib import admin

from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "name", "type", "status", "owner", "department", "warranty_expiry")
    list_filter = ("type", "status", "department")
    search_fields = ("asset_tag", "name", "serial_number")
