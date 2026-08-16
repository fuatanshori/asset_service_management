from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from equipment.models import Equipment
from .forms import LogFilterForm, MaintenanceLogForm, MaintenanceScheduleForm, ScheduleFilterForm
from .models import MaintenanceLog, MaintenanceSchedule, sync_equipment_status_from_remaining_logs


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

    context = {"active_page": "maintenance", "form": form, "schedule_list": qs}
    return render(request, "maintenance/schedule_list.html", context)


def schedule_add(request):
    """Buat jadwal baru. Riwayatnya (MaintenanceLog) otomatis dibuat kosong
    di belakang layar (untuk relasi 1:1), TAPI tidak dipaksa diisi sekarang
    juga — cuma opsi, bisa diisi kapan saja lewat "Edit Riwayat"."""
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
            return redirect("equipment:equipment_detail", pk=selected_equipment.pk)
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
            return redirect("schedule_list")
    else:
        form = MaintenanceScheduleForm(initial=initial)
    return render(
        request,
        "maintenance/schedule_form.html",
        {
            "form": form,
            "active_page": "maintenance",
            "mode": "add",
            "selected_equipment_label": str(selected_equipment) if selected_equipment else "",
        },
    )


def schedule_edit(request, pk):
    schedule = get_object_or_404(MaintenanceSchedule, pk=pk)
    if not schedule.is_editable:
        messages.error(
            request,
            f'Jadwal untuk "{schedule.equipment.name}" ini bukan yang terbaru — '
            "data lama bersifat arsip dan tidak bisa diedit lagi (masih bisa dihapus).",
        )
        return redirect("schedule_list")

    if request.method == "POST":
        form = MaintenanceScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "Jadwal maintenance berhasil diperbarui.")
            return redirect("schedule_list")
    else:
        form = MaintenanceScheduleForm(instance=schedule)
    return render(
        request,
        "maintenance/schedule_form.html",
        {
            "form": form,
            "active_page": "maintenance",
            "mode": "edit",
            "schedule": schedule,
            "selected_equipment_label": str(schedule.equipment),
        },
    )


def schedule_delete(request, pk):
    """Hapus jadwal (riwayatnya ikut kehapus via cascade). Status barang
    dihitung ulang dari jadwal-jadwal lain yang masih tersisa untuk
    equipment yang sama."""
    schedule = MaintenanceSchedule.objects.filter(pk=pk).first()
    if schedule is None:
        messages.warning(request, "Jadwal ini sudah tidak ada (mungkin sudah dihapus sebelumnya).")
        return redirect("schedule_list")

    if request.method == "POST":
        equipment = schedule.equipment
        schedule.delete()
        sync_equipment_status_from_remaining_logs(equipment)
        messages.success(request, "Jadwal maintenance berhasil dihapus.")
        return redirect("schedule_list")
    return render(
        request,
        "maintenance/schedule_confirm_delete.html",
        {"schedule": schedule, "active_page": "maintenance"},
    )


def schedule_calendar(request):
    return render(request, "maintenance/schedule_calendar.html", {"active_page": "maintenance"})


COLOR_HEX = {"green": "#328A63", "amber": "#C97A2E", "red": "#C0483F", "brand": "#2A5C8A", "muted": "#5E6B7C"}


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

    context = {"active_page": "history", "form": form, "log_list": qs}
    return render(request, "maintenance/log_list.html", context)


def log_edit(request, pk):
    log = get_object_or_404(MaintenanceLog, pk=pk)
    if not log.is_editable:
        messages.error(
            request,
            f'Riwayat untuk "{log.schedule.equipment.name}" ini bukan yang terbaru — '
            "data lama bersifat arsip dan tidak bisa diedit lagi (masih bisa dihapus).",
        )
        return redirect("schedule_list")

    if request.method == "POST":
        form = MaintenanceLogForm(request.POST, request.FILES, instance=log)
        if form.is_valid():
            form.save()
            messages.success(request, "Riwayat maintenance berhasil diperbarui.")
            return redirect("schedule_list")
    else:
        form = MaintenanceLogForm(instance=log)
    return render(
        request,
        "maintenance/log_form.html",
        {"form": form, "active_page": "history", "schedule": log.schedule},
    )