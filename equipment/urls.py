# equipment/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("equipment/", views.equipment_list, name="equipment_list"),
    path("equipment/add/", views.equipment_add, name="equipment_add"),
    path("equipment/import/", views.equipment_import, name="equipment_import"),
    # path("equipment/bulk-delete/", views.equipment_bulk_delete, name="equipment_bulk_delete"),
    path("equipment/<int:pk>/", views.equipment_detail, name="equipment_detail"),
    path("equipment/<int:pk>/edit/", views.equipment_edit, name="equipment_edit"),
    path("equipment/<int:pk>/delete/", views.equipment_delete, name="equipment_delete"),
    path("equipment/<int:pk>/qrcode/", views.equipment_qrcode, name="equipment_qrcode"),
    path("equipment/<int:pk>/qrcode/print/", views.equipment_qrcode_print, name="equipment_qrcode_print"),
    path("equipment/search/", views.equipment_search, name="equipment_search"),
    path("equipment/export/", views.equipment_export, name="equipment_export"),
    path("equipment/map/", views.equipment_map, name="equipment_map"),
    path("equipment/qrcode/print-bulk/", views.equipment_qrcode_print_bulk, name="equipment_qrcode_print_bulk"),
    path("scan/", views.scan_view, name="scan"),
]