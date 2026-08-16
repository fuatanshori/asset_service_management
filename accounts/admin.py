# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Info Staff", {"fields": ("full_name", "unit_kerja")}),
    )
    list_display = ("username", "full_name", "unit_kerja", "is_staff", "is_active")
    search_fields = ("username", "full_name", "unit_kerja", "email")