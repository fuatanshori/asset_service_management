#maintenance/analytics.py

"""Analitik seputar jadwal & riwayat maintenance — biaya, breakdown jenis,
hasil kerja, peringkat barang/teknisi, dan jadwal telat."""

from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from equipment.models import Equipment
from .models import MaintenanceLog, MaintenanceSchedule


def _filter_logs(qs, date_from=None, date_to=None):
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def _filter_schedules(qs, date_from=None, date_to=None):
    if date_from:
        qs = qs.filter(scheduled_date__gte=date_from)
    if date_to:
        qs = qs.filter(scheduled_date__lte=date_to)
    return qs


def get_cost_by_month(date_from=None, date_to=None, limit_months=12):
    qs = _filter_logs(MaintenanceLog.objects.all(), date_from, date_to)
    rows = list(
        qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total_cost=Sum("cost"))
        .order_by("month")
    )
    rows = [r for r in rows if r["month"]]
    if not date_from and not date_to:
        rows = rows[-limit_months:]
    return {
        "labels": [r["month"].strftime("%b %Y") for r in rows],
        "values": [float(r["total_cost"] or 0) for r in rows],
    }


def get_maintenance_type_breakdown(date_from=None, date_to=None):
    qs = _filter_schedules(MaintenanceSchedule.objects.all(), date_from, date_to)
    rows = qs.values("maintenance_type").annotate(total=Count("id")).order_by("-total")
    label_map = dict(MaintenanceSchedule.TYPE_CHOICES)
    return [{"label": label_map.get(r["maintenance_type"], r["maintenance_type"]), "total": r["total"]} for r in rows]


def get_result_breakdown(date_from=None, date_to=None):
    qs = _filter_logs(MaintenanceLog.objects.all(), date_from, date_to)
    rows = qs.values("result").annotate(total=Count("id")).order_by("-total")
    label_map = dict(MaintenanceLog.RESULT_CHOICES)
    return [{"label": label_map.get(r["result"], r["result"]), "total": r["total"]} for r in rows]


def get_overdue_schedules(limit=8):
    today = timezone.localdate()
    qs = (
        MaintenanceSchedule.objects.select_related("equipment", "log")
        .filter(scheduled_date__lt=today)
        .filter(Q(log__isnull=True) | Q(log__result__in=[MaintenanceLog.RESULT_PENDING, MaintenanceLog.RESULT_IN_PROGRESS]))
        .order_by("scheduled_date")
    )
    return qs[:limit], qs.count()


def get_service_ranking_queryset(date_from=None, date_to=None):
    schedules = _filter_schedules(MaintenanceSchedule.objects.all(), date_from, date_to)
    equipment_ids = schedules.values_list("equipment_id", flat=True)
    return (
        Equipment.objects.filter(pk__in=equipment_ids)
        .annotate(service_count=Count("maintenance_schedules", filter=Q(maintenance_schedules__in=schedules)))
        .filter(service_count__gt=0)
        .order_by("-service_count", "name")
    )


def get_top_serviced_equipment(date_from=None, date_to=None, limit=5):
    return get_service_ranking_queryset(date_from, date_to)[:limit]


def get_technician_ranking_queryset(date_from=None, date_to=None):
    qs = _filter_logs(MaintenanceLog.objects.exclude(technician=""), date_from, date_to)
    return (
        qs.values("technician")
        .annotate(total=Count("id"), total_cost=Sum("cost"))
        .order_by("-total", "technician")
    )


def get_top_technicians(date_from=None, date_to=None, limit=5):
    return list(get_technician_ranking_queryset(date_from, date_to)[:limit])


def get_cost_summary():
    """Selalu angka sepanjang waktu — sengaja tidak difilter tanggal.
    Cuma ngitung riwayat yang completed_date-nya udah keisi (beneran
    Selesai/Gagal)."""
    today = timezone.localdate()
    qs = MaintenanceLog.objects.exclude(completed_date__isnull=True)
    agg = qs.aggregate(all_time=Sum("cost"), avg_per_service=Avg("cost"))
    this_year = qs.filter(completed_date__year=today.year).aggregate(total=Sum("cost"))["total"] or 0
    this_month = qs.filter(completed_date__year=today.year, completed_date__month=today.month).aggregate(total=Sum("cost"))["total"] or 0
    return {
        "all_time": float(agg["all_time"] or 0),
        "avg_per_service": float(agg["avg_per_service"] or 0),
        "this_year": float(this_year),
        "this_month": float(this_month),
    }


def get_month_over_month_cost():
    today = timezone.localdate()
    this_month_start = today.replace(day=1)
    if this_month_start.month == 1:
        last_month_start = this_month_start.replace(year=this_month_start.year - 1, month=12)
    else:
        last_month_start = this_month_start.replace(month=this_month_start.month - 1)
    last_month_end = this_month_start - timedelta(days=1)

    completed_logs = MaintenanceLog.objects.exclude(completed_date__isnull=True)
    this_month_total = float(
        completed_logs.filter(completed_date__gte=this_month_start, completed_date__lte=today)
        .aggregate(total=Sum("cost"))["total"] or 0
    )
    last_month_total = float(
        completed_logs.filter(completed_date__gte=last_month_start, completed_date__lte=last_month_end)
        .aggregate(total=Sum("cost"))["total"] or 0
    )

    if last_month_total > 0:
        change_pct = round((this_month_total - last_month_total) / last_month_total * 100)
    else:
        change_pct = None

    return {"this_month": this_month_total, "last_month": last_month_total, "change_pct": change_pct}


def get_cost_trend(date_from=None, date_to=None, limit_months=12):
    qs = MaintenanceLog.objects.exclude(completed_date__isnull=True)
    if date_from:
        qs = qs.filter(completed_date__gte=date_from)
    if date_to:
        qs = qs.filter(completed_date__lte=date_to)
    rows = list(
        qs.annotate(month=TruncMonth("completed_date"))
        .values("month")
        .annotate(total_cost=Sum("cost"))
        .order_by("month")
    )
    if not date_from and not date_to:
        rows = rows[-limit_months:]
    return {
        "labels": [r["month"].strftime("%b %Y") for r in rows],
        "values": [float(r["total_cost"] or 0) for r in rows],
    }


def get_cost_by_equipment(date_from=None, date_to=None, limit=10):
    qs = MaintenanceLog.objects.exclude(completed_date__isnull=True)
    if date_from:
        qs = qs.filter(completed_date__gte=date_from)
    if date_to:
        qs = qs.filter(completed_date__lte=date_to)
    rows = (
        qs.values("schedule__equipment__id", "schedule__equipment__name", "schedule__equipment__serial_number")
        .annotate(total_cost=Sum("cost"), service_count=Count("id"))
        .order_by("-total_cost")[:limit]
    )
    return list(rows)


def get_stale_equipment(months_threshold=6, limit=10):
    cutoff = timezone.localdate() - timedelta(days=months_threshold * 30)
    recently_serviced_ids = (
        MaintenanceLog.objects.exclude(completed_date__isnull=True)
        .filter(completed_date__gte=cutoff)
        .values_list("schedule__equipment_id", flat=True)
        .distinct()
    )
    return Equipment.objects.exclude(pk__in=recently_serviced_ids).order_by("name")[:limit]