# reports/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("laporan/", views.report_view, name="report"),
    path("laporan/detail/", views.report_detail_redirect, name="report_detail"),
    path("laporan/export-lengkap/", views.report_export_full, name="report_export_full"),
]