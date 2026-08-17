# equipment/views.py

import io
import json

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from openpyxl import Workbook

from .forms import EquipmentFilterForm, EquipmentForm
from .models import Equipment


# ---------- Export helpers (dipakai bareng equipment_export & reports.report_export_full) ----------

EQUIPMENT_EXPORT_HEADERS = [
    "Nama", "Merk", "Tipe", "No. Seri", "Tahun Perolehan", "Status",
    "Lokasi", "Latitude", "Longitude", "Keterangan", "Dibuat Pada", "Diubah Pada",
]


def equipment_export_row(item):
    return [
        item.name, item.brand, item.model_type, item.serial_number, item.acquisition_year,
        item.get_status_display(), item.location_name,
        float(item.latitude) if item.latitude is not None else "",
        float(item.longitude) if item.longitude is not None else "",
        item.notes,
        timezone.localtime(item.created_at).strftime("%d-%m-%Y %H:%M"),
        timezone.localtime(item.updated_at).strftime("%d-%m-%Y %H:%M"),
    ]


# ---------- Equipment ----------

@login_required
def equipment_list(request):
    form = EquipmentFilterForm(request.GET or None)
    qs = Equipment.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            q = data["q"]
            qs = qs.filter(
                Q(name__icontains=q) | Q(brand__icontains=q)
                | Q(model_type__icontains=q) | Q(serial_number__icontains=q)
            )
        if data["brand"]:
            qs = qs.filter(brand__iexact=data["brand"])
        if data["model_type"]:
            qs = qs.filter(model_type__iexact=data["model_type"])
        if data["acquisition_year"]:
            qs = qs.filter(acquisition_year=data["acquisition_year"])
        if data["status"]:
            qs = qs.filter(status=data["status"])

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    querydict = request.GET.copy()
    querydict.pop("page", None)

    context = {
        "active_page": "equipment",
        "form": form,
        "page_obj": page_obj,
        "equipment_list": page_obj.object_list,
        "filter_querystring": querydict.urlencode(),
        "brand_choices": Equipment.objects.values_list("brand", flat=True).distinct(),
        "model_type_choices": Equipment.objects.values_list("model_type", flat=True).distinct(),
        "year_choices": Equipment.objects.values_list("acquisition_year", flat=True)
        .distinct()
        .order_by("-acquisition_year"),
    }
    return render(request, "equipment/equipment_list.html", context)


def equipment_detail(request, pk):
    """Sengaja PUBLIK (tidak login_required) — halaman ini yang dituju QR
    code fisik di barang, jadi siapapun yang scan bisa langsung lihat info
    & riwayat tanpa perlu login dulu. Read-only: tombol aksi (Edit,
    Tambah, dst) di template disembunyikan untuk pengunjung yang belum
    login lewat pengecekan {% if user.is_authenticated %}."""
    item = get_object_or_404(Equipment, pk=pk)
    context = {
        "active_page": "equipment",
        "equipment": item,
        "schedule_list": item.maintenance_schedules.select_related("log").all()[:10],
    }
    return render(request, "equipment/equipment_detail.html", context)


@login_required
def equipment_add(request):
    if request.method == "POST":
        form = EquipmentForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(request, f'Barang "{item.name}" berhasil ditambahkan.')
            return redirect("equipment_list")
    else:
        form = EquipmentForm()
    return render(
        request, "equipment/equipment_form.html", {"form": form, "active_page": "equipment", "mode": "add"}
    )


@login_required
def equipment_edit(request, pk):
    item = get_object_or_404(Equipment, pk=pk)
    if request.method == "POST":
        form = EquipmentForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'Barang "{item.name}" berhasil diperbarui.')
            return redirect("equipment_list")
    else:
        form = EquipmentForm(instance=item)
    return render(
        request,
        "equipment/equipment_form.html",
        {"form": form, "active_page": "equipment", "mode": "edit", "equipment": item},
    )


@login_required
def equipment_delete(request, pk):
    item = get_object_or_404(Equipment, pk=pk)
    if request.method == "POST":
        name = item.name
        item.delete()
        messages.success(request, f'Barang "{name}" berhasil dihapus.')
        return redirect("equipment_list")
    return render(
        request, "equipment/equipment_confirm_delete.html", {"equipment": item, "active_page": "equipment"}
    )


@login_required
def equipment_search(request):
    """AJAX endpoint untuk search-as-you-type di form Jadwal (app maintenance).
    Barang yang sedang "Dalam Perbaikan" atau "Dijadwalkan" sengaja tidak
    ikut muncul, karena tidak boleh ditambahkan jadwal baru (cegah
    double-booking). Login-protected karena cuma dipakai dari dalam form
    Jadwal yang juga wajib login."""
    q = request.GET.get("q", "").strip()
    qs = Equipment.objects.exclude(status__in=[Equipment.STATUS_UNDER_REPAIR, Equipment.STATUS_SCHEDULED])
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(brand__icontains=q) | Q(model_type__icontains=q)
            | Q(serial_number__icontains=q)
        )
    # "label" dipertahankan buat ngisi kotak input pas dipilih (format
    # ringkas, dipakai juga di selected_equipment_label view lain).
    # Field lainnya buat nampilin detail lebih informatif di dropdown
    # hasil pencarian — biar gampang bedain barang yang namanya mirip.
    results = [
        {
            "id": item.pk,
            "label": str(item),
            "name": item.name,
            "serial_number": item.serial_number,
            "brand": item.brand,
            "model_type": item.model_type,
            "location_name": item.location_name,
        }
        for item in qs[:10]
    ]
    return JsonResponse({"results": results})


@login_required
def equipment_export(request):
    qs = Equipment.objects.all()
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="data_barang.xlsx"'

    wb = Workbook()
    ws = wb.active
    ws.title = "Data Barang"
    ws.append(EQUIPMENT_EXPORT_HEADERS)
    for item in qs:
        ws.append(equipment_export_row(item))
    wb.save(response)
    return response


@login_required
def equipment_map(request):
    items = Equipment.objects.filter(latitude__isnull=False, longitude__isnull=False)
    markers = [
        {
            "id": item.pk,
            "name": item.name,
            "lat": float(item.latitude),
            "lng": float(item.longitude),
            "status": item.get_status_display(),
            "status_color": item.status_color,
            "url": item.get_absolute_url(),
        }
        for item in items
    ]
    return render(
        request, "equipment/equipment_map.html",
        {"markers_json": json.dumps(markers), "active_page": "equipment"},
    )


def equipment_qrcode(request, pk):
    """Sengaja PUBLIK — ini gambar QR code itu sendiri, di-embed lewat
    <img> di halaman Detail Barang yang juga publik. Kalau ini
    login_required, gambarnya nggak bakal muncul buat pengunjung yang
    belum login."""
    item = get_object_or_404(Equipment, pk=pk)
    detail_url = request.build_absolute_uri(item.get_absolute_url())
    try:
        box_size = int(request.GET.get("size", 8))
    except ValueError:
        box_size = 8
    box_size = max(2, min(box_size, 20))

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(detail_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#14213D", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
def equipment_qrcode_print(request, pk):
    item = get_object_or_404(Equipment, pk=pk)
    return render(request, "equipment/equipment_qrcode_print.html", {"equipment": item})


@login_required
def equipment_qrcode_print_bulk(request):
    ids = request.GET.getlist("ids")
    items = Equipment.objects.filter(pk__in=ids)
    return render(request, "equipment/equipment_qrcode_print_bulk.html", {"equipment_list": items})


# ---------- Scan ----------

def scan_view(request):
    """Sengaja PUBLIK — halaman scan kamera dipakai di lapangan sebelum
    tentu sempat login. Link "Cari Manual" di halaman ini mengarah ke
    equipment_list yang wajib login, jadi pengunjung anonim yang pakai
    fitur itu bakal diarahkan ke halaman login dulu — itu sesuai desain."""
    return render(request, "equipment/scan.html", {"active_page": "scan"})