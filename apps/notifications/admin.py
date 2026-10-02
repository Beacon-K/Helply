from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "kind", "title", "ticket", "is_read", "emailed")
    list_filter = ("kind", "is_read", "emailed")
    search_fields = ("title", "body", "recipient__username")
    raw_id_fields = ("ticket",)
