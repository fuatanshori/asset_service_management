from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from openpyxl import Workbook

from equipment.models import Equipment
from .forms import LogFilterForm, MaintenanceLogForm, MaintenanceScheduleForm, ScheduleFilterForm
from .models import MaintenanceLog, MaintenanceSchedule, sync_equipment_status


def _safe_next_url(request, fallback):
    """Balik ke URL asal (dikirim lewat POST/GET field "next") kalau ada
    dan aman (nggak diarahin ke domain luar) — kalau nggak ada, pakai
    fallback default."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return fallback


def _active_page_for_next(request, default):
    """Tab navbar yang nyala ngikutin halaman ASAL (dari next=...), bukan
    selalu jenis form yang lagi dibuka. Jadi kalau lagi kerja di Data
    Barang terus edit/hapus Jadwal atau Riwayat terkait, tab "Data Barang"
    tetap nyala — nggak loncat ke "Jadwal Maintenance"/"Riwayat
    Maintenance". Kalau tidak ada next (akses langsung), pakai default
    sesuai jenis form."""
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    path = next_url.split("?")[0]
    if path.startswith("/equipment/"):
        return "equipment"
    if path.startswith("/schedules/"):
        return "maintenance"
    if path.startswith("/logs/"):
        return "history"
    return default


# ---------- Export helpers (dipakai bareng schedule_export & reports.report_export_full) ----------

SCHEDULE_EXPORT_HEADERS = [
    "Barang", "No. Seri", "Merk", "Tipe", "Tanggal Jadwal", "Jenis Perawatan",
    "Catatan Jadwal", "Teknisi", "Tindakan", "Hasil", "Biaya", "Tanggal Selesai", "Dibuat Pada",
]


def schedule_export_row(s):
    log = s.log
    return [
        s.equipment.name,
        s.equipment.serial_number,
        s.equipment.brand,
        s.equipment.model_type,
        s.scheduled_date.strftime("%d-%m-%Y"),
        s.get_maintenance_type_display(),
        s.notes,
        log.technician if log else "",
        log.action_taken if log else "",
        log.get_result_display() if log else "",
        float(log.cost) if log else 0,
        log.completed_date.strftime("%d-%m-%Y") if log and log.completed_date else "",
        timezone.localtime(s.created_at).strftime("%d-%m-%Y %H:%M"),
    ]


# ---------- Maintenance schedule ----------

@login_required
def schedule_list(request):
    form = ScheduleFilterForm(request.GET or None)
    qs = MaintenanceSchedule.objects.select_related("equipment", "log").all()
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            q = data["q"]
            qs = qs.filter(Q(equipment__name__icontains=q) | Q(equipment__brand__icontains=q))
        if data["maintenance_type"]:
            qs = qs.filter(maintenance_type=data["maintenance_type"])
        if data["result"]:
            qs = qs.filter(log__result=data["result"])
        if data["date_from"]:
            qs = qs.filter(scheduled_date__gte=data["date_from"])
        if data["date_to"]:
            qs = qs.filter(scheduled_date__lte=data["date_to"])

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    querydict = request.GET.copy()
    querydict.pop("page", None)

    context = {
        "active_page": "maintenance",
        "form": form,
        "page_obj": page_obj,
        "schedule_list": page_obj.object_list,
        "filter_querystring": querydict.urlencode(),
    }
    return render(request, "maintenance/schedule_list.html", context)


@login_required
def schedule_add(request):
    """Buat jadwal baru. Default balik ke daftar Jadwal — TAPI kalau
    diakses dengan ?next=<url>, balik ke situ (misal dari halaman Detail
    Barang)."""
    initial = {}
    equipment_id = request.GET.get("equipment")
    selected_equipment = None
    if equipment_id:
        selected_equipment = Equipment.objects.filter(pk=equipment_id).first()
        if selected_equipment and selected_equipment.status in (
            Equipment.STATUS_UNDER_REPAIR, Equipment.STATUS_SCHEDULED
        ):
            messages.error(
                request,
                f'Barang "{selected_equipment.name}" sedang berstatus '
                f'"{selected_equipment.get_status_display()}" — tidak bisa ditambahkan jadwal baru.',
            )
            return redirect(_safe_next_url(request, reverse("equipment_detail", args=[selected_equipment.pk])))
        initial["equipment"] = equipment_id
    if request.GET.get("type") == "repair":
        initial["maintenance_type"] = MaintenanceSchedule.TYPE_REPAIR

    if request.method == "POST":
        form = MaintenanceScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Jadwal maintenance berhasil ditambahkan. Status barang otomatis "Dijadwalkan" — '
                'riwayat pengerjaan bisa diisi kapan saja lewat tombol "Edit Riwayat".',
            )
            return redirect(_safe_next_url(request, reverse("schedule_list")))
    else:
        form = MaintenanceScheduleForm(initial=initial)
    return render(
        request,
        "maintenance/schedule_form.html",
        {
            "form": form,
            "active_page": _active_page_for_next(request, "maintenance"),
            "mode": "add",
            "selected_equipment_label": str(selected_equipment) if selected_equipment else "",
            "next_url": request.GET.get("next", ""),
        },
    )


@login_required
def schedule_edit(request, pk):
    """Default balik ke daftar Jadwal, kecuali diakses dengan
    ?next=<url> (misal dari Detail Barang)."""
    schedule = get_object_or_404(MaintenanceSchedule, pk=pk)
    if request.method == "POST":
        form = MaintenanceScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "Jadwal maintenance berhasil diperbarui.")
            return redirect(_safe_next_url(request, reverse("schedule_list")))
    else:
        form = MaintenanceScheduleForm(instance=schedule)
    return render(
        request,
        "maintenance/schedule_form.html",
        {
            "form": form,
            "active_page": _active_page_for_next(request, "maintenance"),
            "mode": "edit",
            "schedule": schedule,
            "selected_equipment_label": str(schedule.equipment),
            "next_url": request.GET.get("next", ""),
        },
    )


@login_required
def schedule_delete(request, pk):
    """Hapus jadwal. Default balik ke daftar Jadwal, kecuali diakses
    dengan ?next=<url>."""
    schedule = MaintenanceSchedule.objects.filter(pk=pk).first()
    if schedule is None:
        messages.warning(request, "Jadwal ini sudah tidak ada (mungkin sudah dihapus sebelumnya).")
        return redirect(_safe_next_url(request, reverse("schedule_list")))

    if request.method == "POST":
        equipment = schedule.equipment
        schedule.delete()
        sync_equipment_status(equipment)
        messages.success(request, "Jadwal maintenance berhasil dihapus.")
        return redirect(_safe_next_url(request, reverse("schedule_list")))
    return render(
        request,
        "maintenance/schedule_confirm_delete.html",
        {
            "schedule": schedule,
            "active_page": _active_page_for_next(request, "maintenance"),
            "next_url": request.GET.get("next", ""),
        },
    )


@login_required
def schedule_calendar(request):
    return render(request, "maintenance/schedule_calendar.html", {"active_page": "maintenance"})


COLOR_HEX = {"green": "#328A63", "amber": "#C97A2E", "red": "#C0483F", "brand": "#2A5C8A", "muted": "#5E6B7C"}


@login_required
def schedule_calendar_events(request):
    events = []
    for s in MaintenanceSchedule.objects.select_related("equipment", "log").all():
        color = COLOR_HEX.get(s.log.result_color, "#2A5C8A") if s.log else "#2A5C8A"
        events.append({
            "title": f"{s.equipment.name} — {s.get_maintenance_type_display()}",
            "start": s.scheduled_date.isoformat(),
            "url": reverse("schedule_edit", args=[s.pk]),
            "color": color,
        })
    return JsonResponse(events, safe=False)


@login_required
def schedule_export(request):
    qs = MaintenanceSchedule.objects.select_related("equipment", "log").all()
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        qs = qs.filter(scheduled_date__gte=date_from)
    if date_to:
        qs = qs.filter(scheduled_date__lte=date_to)

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="jadwal_maintenance.xlsx"'

    wb = Workbook()
    ws = wb.active
    ws.title = "Jadwal & Riwayat"
    ws.append(SCHEDULE_EXPORT_HEADERS)
    for s in qs:
        ws.append(schedule_export_row(s))
    wb.save(response)
    return response


# ---------- Maintenance log (riwayat) ----------

@login_required
def log_list(request):
    form = LogFilterForm(request.GET or None)
    qs = MaintenanceLog.objects.select_related("schedule__equipment").all()
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            q = data["q"]
            qs = qs.filter(Q(schedule__equipment__name__icontains=q) | Q(technician__icontains=q))
        if data["result"]:
            qs = qs.filter(result=data["result"])
        if data["year"]:
            qs = qs.filter(date__year=data["year"])

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    querydict = request.GET.copy()
    querydict.pop("page", None)

    context = {
        "active_page": "history",
        "form": form,
        "page_obj": page_obj,
        "log_list": page_obj.object_list,
        "filter_querystring": querydict.urlencode(),
    }
    return render(request, "maintenance/log_list.html", context)


@login_required
def log_edit(request, pk):
    """Default balik ke daftar Riwayat, kecuali diakses dengan
    ?next=<url> (misal dari Detail Barang atau daftar Jadwal)."""
    log = get_object_or_404(MaintenanceLog, pk=pk)
    if request.method == "POST":
        form = MaintenanceLogForm(request.POST, request.FILES, instance=log)
        if form.is_valid():
            form.save()
            messages.success(request, "Riwayat maintenance berhasil diperbarui.")
            return redirect(_safe_next_url(request, reverse("log_list")))
    else:
        form = MaintenanceLogForm(instance=log)
    return render(
        request,
        "maintenance/log_form.html",
        {
            "form": form,
            "active_page": _active_page_for_next(request, "history"),
            "schedule": log.schedule,
            "next_url": request.GET.get("next", ""),
        },
    )


def log_detail(request, pk):
    """Detail lengkap satu riwayat maintenance — termasuk biaya dan foto
    dokumentasi (before/after/kwitansi). Sengaja PUBLIK (tidak
    login_required) — desain yang sama dengan equipment_detail &
    equipment_qrcode, biar siapapun yang scan QR bisa lihat riwayat
    lengkap tanpa perlu login. Tombol Edit tetap dikunci login lewat
    {% if user.is_authenticated %} di template."""
    log = get_object_or_404(
        MaintenanceLog.objects.select_related("schedule__equipment"), pk=pk
    )
    schedule = log.schedule
    equipment = schedule.equipment

    return render(request, "maintenance/log_detail.html", {
        "log": log,
        "schedule": schedule,
        "equipment": equipment,
        "next_url": request.GET.get("next", ""),
        "active_page": "equipment" if request.GET.get("from") == "equipment" else "history",
    })