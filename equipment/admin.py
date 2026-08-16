# equipment/admin.py

from django.contrib import admin
from .models import Equipment


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("name", "serial_number", "brand", "model_type", "acquisition_year", "status")
    list_filter = ("status", "brand", "acquisition_year")
    search_fields = ("name", "serial_number", "brand", "model_type")