from django.contrib import admin

from .models import AISuggestion


@admin.register(AISuggestion)
class AISuggestionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "ticket", "backend", "confidence", "applied", "accepted")
    list_filter = ("kind", "backend", "applied", "accepted")
    readonly_fields = ("created_at",)
