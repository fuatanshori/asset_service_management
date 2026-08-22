# equipment/analytics.py

from .models import Equipment
from django.utils import timezone

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

def get_equipment_age_analysis():
    """Analisis umur barang berdasarkan acquisition_year. Barang tanpa
    tahun perolehan (null — banyak kejadian di data hasil import Excel
    lama) SENGAJA dikeluarkan dari perhitungan umur, rata-rata, dan
    daftar "barang tertua" — nggak ada cara ngitung umur tanpa tau
    kapan diperoleh. Jumlahnya tetap dilaporkan terpisah
    (without_year_count) sebagai catatan kelengkapan data.

    Tiap bucket umur SEKARANG bawa daftar barangnya sendiri-sendiri
    (bukan cuma angka) — dipakai buat fitur drill-down di Laporan:
    klik salah satu kotak umur, langsung kelihatan daftar barangnya."""
    current_year = timezone.localdate().year
    with_year_qs = Equipment.objects.exclude(acquisition_year__isnull=True).order_by("acquisition_year")
    without_year_count = Equipment.objects.filter(acquisition_year__isnull=True).count()
    with_year_count = with_year_qs.count()

    # Warna dipetakan manual (bukan dibangun dinamis di template) biar
    # class Tailwind-nya tetap literal & aman ke-compile.
    buckets = [
        {"label": "0–2 Tahun", "count": 0, "text_class": "text-green", "bg_hex": "#E1F1E9", "items": []},
        {"label": "3–5 Tahun", "count": 0, "text_class": "text-brand", "bg_hex": "#E2E9F1", "items": []},
        {"label": "6–10 Tahun", "count": 0, "text_class": "text-amber", "bg_hex": "#F7E9D8", "items": []},
        {"label": ">10 Tahun", "count": 0, "text_class": "text-red", "bg_hex": "#F8E2E0", "items": []},
    ]
    total_age = 0

    for item in with_year_qs:
        age = current_year - item.acquisition_year
        total_age += age
        entry = {
            "pk": item.pk,
            "name": item.name,
            "serial_number": item.serial_number or "",
            "acquisition_year": item.acquisition_year,
            "age": age,
            "url": item.get_absolute_url(),
        }
        if age <= 2:
            bucket_idx = 0
        elif age <= 5:
            bucket_idx = 1
        elif age <= 10:
            bucket_idx = 2
        else:
            bucket_idx = 3
        buckets[bucket_idx]["count"] += 1
        buckets[bucket_idx]["items"].append(entry)

    avg_age = round(total_age / with_year_count, 1) if with_year_count else 0

    # Umur dihitung di Python (bukan di template) biar nggak perlu
    # aritmatika aneh lewat filter Django.
    oldest_equipment = [
        {"item": item, "age": current_year - item.acquisition_year}
        for item in with_year_qs[:10]
    ]

    return {
        "with_year_count": with_year_count,
        "without_year_count": without_year_count,
        "buckets": buckets,
        "avg_age": avg_age,
        "oldest_equipment": oldest_equipment,
    }