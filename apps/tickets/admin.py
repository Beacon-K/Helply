from django.contrib import admin

from .models import Category, Satisfaction, Ticket, TicketComment, TicketEvent


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    can_delete = False
    readonly_fields = ("created_at", "actor", "kind", "from_status", "to_status", "note")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "status", "priority", "category", "assignee", "requester",
                    "resolution_due_at", "sla_breached")
    list_filter = ("status", "priority", "category", "sla_breached", "ai_classified")
    search_fields = ("title", "description")
    readonly_fields = ("priority", "created_at", "updated_at")
    inlines = [TicketCommentInline, TicketEventInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "default_group", "is_active")
    list_filter = ("is_active",)


@admin.register(Satisfaction)
class SatisfactionAdmin(admin.ModelAdmin):
    list_display = ("ticket", "rating", "created_at")
