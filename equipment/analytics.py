# equipment/analytics.py

from .models import Equipment


def get_equipment_status_breakdown():
    return {
        "active": Equipment.objects.filter(status=Equipment.STATUS_ACTIVE).count(),
        "scheduled": Equipment.objects.filter(status=Equipment.STATUS_SCHEDULED).count(),
        "under_repair": Equipment.objects.filter(status=Equipment.STATUS_UNDER_REPAIR).count(),
        "damaged": Equipment.objects.filter(status=Equipment.STATUS_DAMAGED).count(),
    }


def get_data_completeness():
    total = Equipment.objects.count()
    if total == 0:
        return {"total": 0, "with_photo_pct": 0, "with_location_pct": 0}
    with_photo = Equipment.objects.exclude(photo="").exclude(photo__isnull=True).count()
    with_location = Equipment.objects.filter(latitude__isnull=False, longitude__isnull=False).count()
    return {
        "total": total,
        "with_photo_pct": round(with_photo / total * 100),
        "with_location_pct": round(with_location / total * 100),
    }