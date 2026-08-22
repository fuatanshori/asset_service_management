# reports/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("laporan/", views.report_view, name="report"),
    path("laporan/detail/", views.report_detail_redirect, name="report_detail"),
    path("laporan/export-lengkap/", views.report_export_full, name="report_export_full"),
    path("laporan/export-ringkasan-barang/", views.report_export_equipment_summary, name="report_export_equipment_summary"),
    path("laporan/analisis-biaya-data/", views.report_cost_analysis_ajax, name="report_cost_analysis_ajax"),
]