#dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/service-ranking/", views.equipment_service_ranking, name="equipment_service_ranking"),
    path("dashboard/technician-ranking/", views.technician_ranking, name="technician_ranking"),
]