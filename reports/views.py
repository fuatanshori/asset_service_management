# reports/views.py
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from openpyxl import Workbook

from equipment.analytics import get_equipment_status_breakdown
from equipment.models import Equipment
from equipment.views import EQUIPMENT_EXPORT_HEADERS, equipment_export_row
from maintenance.analytics import (
    get_cost_by_equipment,
    get_cost_summary,
    get_cost_trend,
    get_month_over_month_cost,
    get_stale_equipment,
)
from maintenance.models import MaintenanceSchedule
from maintenance.views import SCHEDULE_EXPORT_HEADERS, schedule_export_row
from .forms import ReportFilterForm


def report_view(request):
    filter_form = ReportFilterForm(request.GET)
    filter_form.is_valid()
    date_from = filter_form.cleaned_data.get("date_from")
    date_to = filter_form.cleaned_data.get("date_to")

    cost_trend = get_cost_trend(date_from=date_from, date_to=date_to)

    context = {
        "active_page": "report",
        "filter_form": filter_form,
        "is_filtered": bool(date_from or date_to),
        "generated_at": timezone.localtime(),
        "total_equipment": Equipment.objects.count(),
        "status_breakdown": get_equipment_status_breakdown(),
        "cost_summary": get_cost_summary(),
        "cost_mom": get_month_over_month_cost(),
        "cost_trend": list(zip(cost_trend["labels"], cost_trend["values"])),
        "cost_by_equipment": get_cost_by_equipment(date_from=date_from, date_to=date_to, limit=10),
        "stale_equipment": get_stale_equipment(months_threshold=6, limit=10),
    }
    return render(request, "reports/report.html", context)


def report_detail_redirect(request):
    """URL lama /laporan/detail/ sekarang digabung ke /laporan/ —
    redirect biar link/bookmark lama gak 404."""
    return redirect("report")


def report_export_full(request):
    """Excel satu file isinya banyak sheet — pakai helper baris yang sama
    persis dengan equipment_export & schedule_export (app equipment &
    maintenance), biar datanya selalu identik, gak pernah drift beda."""
    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="laporan_lengkap.xlsx"'

    wb = Workbook()

    # --- Sheet 1: Ringkasan ---
    ws = wb.active
    ws.title = "Ringkasan"
    status_breakdown = get_equipment_status_breakdown()
    cost_summary = get_cost_summary()
    ws.append(["Laporan Lengkap Asset Service Management System"])
    ws.append(["Digenerate pada", timezone.localtime().strftime("%d-%m-%Y %H:%M")])
    ws.append([])
    ws.append(["Total Barang", Equipment.objects.count()])
    ws.append(["Barang Aktif", status_breakdown["active"]])
    ws.append(["Barang Dijadwalkan", status_breakdown["scheduled"]])
    ws.append(["Barang Dalam Perbaikan", status_breakdown["under_repair"]])
    ws.append(["Barang Rusak", status_breakdown["damaged"]])
    ws.append([])
    ws.append(["Total Biaya Bulan Ini", cost_summary["this_month"]])
    ws.append(["Total Biaya Tahun Ini", cost_summary["this_year"]])
    ws.append(["Total Biaya Keseluruhan", cost_summary["all_time"]])
    ws.append(["Rata-rata Biaya per Servis", cost_summary["avg_per_service"]])

    # --- Sheet 2: Data Barang ---
    ws2 = wb.create_sheet("Data Barang")
    ws2.append(EQUIPMENT_EXPORT_HEADERS)
    for item in Equipment.objects.all():
        ws2.append(equipment_export_row(item))

    # --- Sheet 3: Jadwal & Riwayat ---
    ws3 = wb.create_sheet("Jadwal & Riwayat")
    ws3.append(SCHEDULE_EXPORT_HEADERS)
    for s in MaintenanceSchedule.objects.select_related("equipment", "log").all():
        ws3.append(schedule_export_row(s))

    # --- Sheet 4: Biaya per Bulan ---
    ws4 = wb.create_sheet("Biaya per Bulan")
    ws4.append(["Bulan", "Total Biaya"])
    cost_trend = get_cost_trend(limit_months=24)
    for label, value in zip(cost_trend["labels"], cost_trend["values"]):
        ws4.append([label, value])

    # --- Sheet 5: Barang Paling Boros Biaya ---
    ws5 = wb.create_sheet("Barang Paling Boros")
    ws5.append(["Nama", "No. Seri", "Jumlah Servis", "Total Biaya"])
    for row in get_cost_by_equipment(limit=20):
        ws5.append([
            row["schedule__equipment__name"],
            row["schedule__equipment__serial_number"],
            row["service_count"],
            float(row["total_cost"] or 0),
        ])

    wb.save(response)
    return response