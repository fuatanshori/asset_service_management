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


def get_maintenance_type_breakdown(date_from=None, date_to=None):
    qs = _filter_schedules(MaintenanceSchedule.objects.all(), date_from, date_to)
    rows = qs.values("maintenance_type").annotate(total=Count("id")).order_by("-total")
    label_map = dict(MaintenanceSchedule.TYPE_CHOICES)
    return [{"label": label_map.get(r["maintenance_type"], r["maintenance_type"]), "total": r["total"]} for r in rows]


# Warna HEX per JENIS hasil kerja — sama persis dengan
# MaintenanceLog.result_color (brand/amber/green/red) supaya konsisten
# di seluruh aplikasi. Ditempel ke result-nya langsung (bukan ke posisi
# di array), biar chart di dashboard nggak salah warna kalau urutan
# baris berubah (get_result_breakdown diurutkan berdasarkan jumlah
# terbanyak — "Gagal" bisa aja jadi baris pertama kalau kebetulan
# jumlahnya paling banyak bulan ini, dan tanpa mapping per-jenis ini,
# dia bakal ke-cat warna yang harusnya buat "Selesai").
RESULT_COLOR_HEX = {
    MaintenanceLog.RESULT_PENDING: "#2A5C8A",
    MaintenanceLog.RESULT_IN_PROGRESS: "#C97A2E",
    MaintenanceLog.RESULT_COMPLETED: "#328A63",
    MaintenanceLog.RESULT_FAILED: "#C0483F",
}


def get_result_breakdown(date_from=None, date_to=None):
    qs = _filter_logs(MaintenanceLog.objects.all(), date_from, date_to)
    rows = qs.values("result").annotate(total=Count("id")).order_by("-total")
    label_map = dict(MaintenanceLog.RESULT_CHOICES)
    return [
        {
            "label": label_map.get(r["result"], r["result"]),
            "total": r["total"],
            "color": RESULT_COLOR_HEX.get(r["result"], "#5E6B7C"),
        }
        for r in rows
    ]


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
    """Perbandingan biaya bulan ini vs bulan lalu — dasar kalimat ringkasan
    otomatis di Ringkasan Eksekutif. Pakai completed_date, bukan date,
    karena biaya baru 'riil' pas kerjaan beneran kelar. change_pct sengaja
    None kalau bulan lalu Rp0 — dari 0 ke berapa pun bukan '100%', itu
    kenaikan tak terhingga, jadi ditampilkan sebagai pernyataan biasa,
    bukan persentase yang menyesatkan."""
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


def _add_months(d, months):
    """Tambah/kurang N bulan dari tanggal d (tanggal di-reset ke 1) —
    buat generate rentang bulan yang berurutan tanpa perlu dependency
    tambahan (python-dateutil dst)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return d.replace(year=year, month=month, day=1)


def get_cost_trend(date_from=None, date_to=None, limit_months=12, all_time=False):
    """Tren biaya per bulan, dikelompokkan berdasarkan completed_date
    (kapan kerjaan beneran kelar), bukan date (tanggal jadwal).

    SATU-SATUNYA fungsi "biaya per bulan" di seluruh aplikasi — dipakai
    Dashboard MAUPUN Laporan (PDF & Excel), biar nggak ada 2 versi
    yang gampang saling drift (sebelumnya Dashboard punya fungsi
    terpisah get_cost_by_month yang salah pakai field `date`, bukan
    `completed_date`, dan nggak ngisi bulan kosong — udah dihapus,
    diganti fungsi ini semua).

    SELALU ngembaliin bulan-bulan yang BERURUTAN tanpa ada yang
    kelewat, termasuk bulan yang nggak ada biayanya sama sekali
    (tampil sebagai 0) — biar "N bulan terakhir" selalu berarti N bulan
    KALENDER beneran, bukan cuma N bulan yang kebetulan punya data.

    date_from/date_to (opsional) nentuin rentang eksplisit. Kalau
    keduanya nggak dikasih:
    - all_time=True: rentangnya dari bulan PALING AWAL ada data
      completed_date sampe bulan berjalan — buat kebutuhan export
      arsip lengkap (misal "Semua Sekaligus"), bukan cuma cuplikan.
    - all_time=False (default): `limit_months` bulan terakhir dari
      bulan berjalan — buat tampilan ringkas (Dashboard, halaman
      Laporan, PDF presentasi)."""
    qs = MaintenanceLog.objects.exclude(completed_date__isnull=True)
    if date_from:
        qs = qs.filter(completed_date__gte=date_from)
    if date_to:
        qs = qs.filter(completed_date__lte=date_to)

    cost_by_month = {
        (r["month"].year, r["month"].month): float(r["total_cost"] or 0)
        for r in qs.annotate(month=TruncMonth("completed_date"))
        .values("month")
        .annotate(total_cost=Sum("cost"))
    }

    today = timezone.localdate()
    end = date_to.replace(day=1) if date_to else today.replace(day=1)

    if date_from:
        start = date_from.replace(day=1)
    elif all_time:
        earliest = qs.order_by("completed_date").values_list("completed_date", flat=True).first()
        start = earliest.replace(day=1) if earliest else end
    else:
        start = _add_months(end, -(limit_months - 1))

    labels, values = [], []
    cursor = start
    while cursor <= end:
        labels.append(cursor.strftime("%b %Y"))
        values.append(cost_by_month.get((cursor.year, cursor.month), 0.0))
        cursor = _add_months(cursor, 1)

    return {"labels": labels, "values": values}


def get_cost_by_equipment(date_from=None, date_to=None, limit=10):
    """Ranking barang paling 'boros' biaya servis — total Rp yang udah
    dihabisin per barang, buat bantu keputusan servis-terus vs ganti baru."""
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
    """Barang yang belum pernah diservis sama sekali, atau udah lebih dari
    N bulan sejak servis terakhirnya kelar — sinyal potensi keabaian.

    Barang berstatus "Dijadwalkan" atau "Dalam Perbaikan" SENGAJA
    dikeluarkan dari daftar ini — kalau statusnya itu, artinya ada
    jadwal maintenance yang lagi AKTIF berjalan buat barang itu (belum
    kelar, makanya completed_date-nya masih kosong dan nggak kehitung
    "baru diservis" di query di bawah). Barang kayak gitu justru lagi
    DITANGANI, bukan diabaikan — jadi nggak masuk akal muncul di daftar
    "belum diservis". Daftar ini khusus buat barang yang MEMANG nggak
    ada aktivitas apapun (status Aktif/Rusak tanpa jadwal berjalan)
    dalam N bulan terakhir.

    Ngembaliin dict {"items": [...], "total_count": N} — BUKAN cuma
    list biasa, biar UI bisa nunjukin total sebenarnya (bisa beda dari
    panjang `items` yang udah dipotong ke `limit`)."""
    cutoff = timezone.localdate() - timedelta(days=months_threshold * 30)
    recently_serviced_ids = (
        MaintenanceLog.objects.exclude(completed_date__isnull=True)
        .filter(completed_date__gte=cutoff)
        .values_list("schedule__equipment_id", flat=True)
        .distinct()
    )
    qs = (
        Equipment.objects.exclude(pk__in=recently_serviced_ids)
        .exclude(status__in=[Equipment.STATUS_SCHEDULED, Equipment.STATUS_UNDER_REPAIR])
        .order_by("name")
    )
    return {"items": list(qs[:limit]), "total_count": qs.count()}


MONTH_NAMES_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def get_available_cost_years():
    """Daftar tahun yang punya riwayat biaya tercatat (completed_date
    bukan kosong), diurutkan terbaru ke terlama. Tahun berjalan SELALU
    disertakan juga walau belum ada datanya sama sekali, biar selector
    tahun di fitur "Cek Biaya per Bulan" nggak pernah kosong pas
    aplikasi baru mulai dipakai."""
    years_with_data = set(
        d.year for d in MaintenanceLog.objects.exclude(completed_date__isnull=True).dates("completed_date", "year")
    )
    years_with_data.add(timezone.localdate().year)
    return sorted(years_with_data, reverse=True)


def get_cost_by_month_for_year(year):
    """Biaya per bulan (Januari–Desember penuh) untuk SATU tahun
    tertentu, termasuk bulan yang belum ada biayanya sama sekali
    (tampil sebagai 0) — beda dari get_cost_trend() yang cuma nampilin
    bulan yang punya data & pakai jendela bergulir (rolling window),
    bukan tahun kalender penuh.

    Sekarang JUGA nyertain breakdown PER-BARANG per bulan
    (by_equipment_per_month) — dipakai widget "Cek Biaya per Tahun &
    Bulan" buat ngitung ulang ranking "Barang Paling Boros" 100% di
    browser (nggak fetch server tiap klik bulan), sesuai kombinasi
    bulan yang lagi dipilih user, termasuk kombinasi yang nggak
    berurutan (misal Januari + Juni doang)."""
    qs = MaintenanceLog.objects.exclude(completed_date__isnull=True).filter(completed_date__year=year)

    by_month = {
        r["month"].month: float(r["total_cost"] or 0)
        for r in qs.annotate(month=TruncMonth("completed_date")).values("month").annotate(total_cost=Sum("cost"))
    }

    by_equipment_per_month = {m: [] for m in range(1, 13)}
    equipment_monthly_rows = (
        qs.annotate(month=TruncMonth("completed_date"))
        .values("month", "schedule__equipment__id", "schedule__equipment__name", "schedule__equipment__serial_number")
        .annotate(total_cost=Sum("cost"), service_count=Count("id"))
    )
    for row in equipment_monthly_rows:
        by_equipment_per_month[row["month"].month].append({
            "id": row["schedule__equipment__id"],
            "name": row["schedule__equipment__name"],
            "serial_number": row["schedule__equipment__serial_number"] or "",
            "total_cost": float(row["total_cost"] or 0),
            "service_count": row["service_count"],
        })

    values = [by_month.get(i, 0) for i in range(1, 13)]
    highest_idx = values.index(max(values)) if any(values) else None

    return {
        "year": year,
        "labels": MONTH_NAMES_ID,
        "short_labels": [m[:3] for m in MONTH_NAMES_ID],
        "values": values,
        "total": sum(values),
        "highest_month_index": highest_idx,  # None kalau seluruh tahun itu Rp0
        # Index 0 = Januari, ..., index 11 = Desember — biar cocok
        # langsung sama index array "values"/"short_labels" di atas.
        "by_equipment_per_month": [by_equipment_per_month[m] for m in range(1, 13)],
    }


def get_cost_by_month_multi_year():
    """Biaya per bulan buat SEMUA tahun yang punya data (lihat
    get_available_cost_years) — dikembalikan sebagai dict {tahun:
    data_bulanan}, siap di-embed sekaligus ke JSON. Ini yang bikin
    fitur "Cek Biaya per Bulan" di halaman Laporan bisa gonta-ganti
    tahun DAN bulan murni lewat JS di browser — nggak ada request baru
    ke server sama sekali pas ganti pilihan, soalnya semua tahun
    datanya udah kekirim sekaligus di awal (termasuk breakdown
    per-barang, buat ngitung ulang Barang Paling Boros)."""
    return {year: get_cost_by_month_for_year(year) for year in get_available_cost_years()}