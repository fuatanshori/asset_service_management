# core/urls.py

from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.contrib.auth import views as auth_views


urlpatterns = [
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("", include("equipment.urls")),
    path("", include("maintenance.urls")),
    path("", include("reports.urls")),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
