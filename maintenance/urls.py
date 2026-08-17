#maintenance/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("schedules/", views.schedule_list, name="schedule_list"),
    path("schedules/add/", views.schedule_add, name="schedule_add"),
    path("schedules/<int:pk>/edit/", views.schedule_edit, name="schedule_edit"),
    path("schedules/<int:pk>/delete/", views.schedule_delete, name="schedule_delete"),
    path("schedules/calendar/", views.schedule_calendar, name="schedule_calendar"),
    path("schedules/calendar/events/", views.schedule_calendar_events, name="schedule_calendar_events"),
    path("schedules/export/", views.schedule_export, name="schedule_export"),
    path("logs/", views.log_list, name="log_list"),
    path("logs/<int:pk>/edit/", views.log_edit, name="log_edit"),
    path("logs/<int:pk>/", views.log_detail, name="log_detail"),
]