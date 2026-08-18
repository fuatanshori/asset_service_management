# reports/views.py
from collections import OrderedDict

from django.contrib.auth.decorators import login_required
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


@login_required
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


@login_required
def report_detail_redirect(request):
    """URL lama /laporan/detail/ sekarang digabung ke /laporan/ —
    redirect biar link/bookmark lama gak 404."""
    return redirect("report")


@login_required
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


def _normalize_for_grouping(value):
    """Bikin nilai jadi case-insensitive & rapi buat keperluan
    perbandingan grouping doang — "Ventilator", "ventilator", dan
    " VENTILATOR " semuanya dianggap sama. None dan string kosong/spasi
    juga disamain jadi None, biar barang yang nggak punya nilai (misal
    nomor seri kosong) tetap konsisten dianggap "sama" sesama yang juga
    kosong. Nilai ASLI (bukan hasil normalize ini) yang tetap dipakai
    buat ditampilkan di baris Excel — normalisasi ini cuma buat nentuin
    mana yang dianggap "duplikat", bukan buat ngubah data yang tersimpan
    atau yang ditampilkan."""
    if value is None:
        return None
    value = str(value).strip().casefold()
    return value or None


def _group_equipment_for_summary(qs):
    """Kelompokkan Equipment berdasarkan (nama, merk, tipe, nomor seri)
    — barang yang persis sama di 4 field ini (case-insensitive, lihat
    _normalize_for_grouping) dianggap "duplikat" dan digabung jadi 1
    baris. Berguna khususnya buat barang generik/nggak punya nomor seri
    unik (banyak kejadian di data hasil import Excel lama), yang tanpa
    ini bakal keliatan sebagai baris berulang identik — termasuk kalau
    cuma beda huruf besar/kecil doang pas ngetik data.

    Field selain 4 itu (status, lokasi, tahun, dst) diambil dari
    ANGGOTA PERTAMA tiap kelompok (diurutkan nama lalu id) — kalau
    field itu beda-beda antar anggota kelompok yang digabung, cuma satu
    nilai representatif yang ditampilkan, bukan semuanya."""
    groups = OrderedDict()
    for item in qs.order_by("name", "pk"):
        key = (
            _normalize_for_grouping(item.name),
            _normalize_for_grouping(item.brand),
            _normalize_for_grouping(item.model_type),
            _normalize_for_grouping(item.serial_number),
        )
        if key not in groups:
            groups[key] = {"representative": item, "count": 0}
        groups[key]["count"] += 1
    return groups


@login_required
def report_export_equipment_summary(request):
    """Export ringkasan Data Barang — barang dengan nama, merk, tipe, &
    nomor seri yang sama persis digabung jadi 1 baris, dengan kolom
    "Total" (paling kanan) menunjukkan berapa banyak barang fisik yang
    digabung ke baris itu. Export terpisah dari equipment_export biasa
    (yang tetap satu baris per barang) — biar kebutuhan detail per-item
    (dipakai juga di report_export_full) tetap nggak kesentuh."""
    qs = Equipment.objects.all()
    groups = _group_equipment_for_summary(qs)

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="ringkasan_barang.xlsx"'

    wb = Workbook()
    ws = wb.active
    ws.title = "Ringkasan Barang"
    ws.append(EQUIPMENT_EXPORT_HEADERS + ["Total"])
    for data in groups.values():
        row = equipment_export_row(data["representative"])
        row.append(data["count"])
        ws.append(row)
    wb.save(response)
    return response