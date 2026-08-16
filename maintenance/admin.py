#maintenance/admin.py

"""Django Admin registration for the maintenance app.

No custom behavior beyond list_display/list_filter/search_fields — but
note that saves made through /admin/ still go through the models' save()
overrides (auto-sync, equipment status updates, completed_date logic),
since Django Admin calls the same model-level save() as everywhere else.
"""

from django.contrib import admin
from .models import MaintenanceSchedule, MaintenanceLog


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ("equipment", "scheduled_date", "maintenance_type")
    list_filter = ("maintenance_type",)
    search_fields = ("equipment__name", "equipment__serial_number")


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ("schedule", "date", "technician", "result", "cost", "completed_date")
    list_filter = ("result",)
    search_fields = ("schedule__equipment__name", "technician")