from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Department, SupportGroup, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "email", "role", "department", "is_active")
    list_filter = ("role", "department", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (("Helply", {"fields": ("role", "department", "phone")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Helply", {"fields": ("role", "department")}),)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(SupportGroup)
class SupportGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    filter_horizontal = ("members",)
