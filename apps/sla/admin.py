from django.contrib import admin

from .models import SLAPolicy


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display = ("priority", "name", "response_minutes", "resolution_minutes", "is_active")
    list_editable = ("response_minutes", "resolution_minutes", "is_active")
