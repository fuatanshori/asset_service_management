# accounts/models.py
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models


class User(AbstractUser):
    """Staff RS Pelabuhan yang mengelola data aset. Extend User bawaan
    Django (bukan bikin tabel profil terpisah) supaya login/permission
    bawaan Django tetap kepakai apa adanya, cuma nambah info staff yang
    relevan.

    Kenapa dibikin app terpisah sekarang, bukan pas beneran butuh nanti:
    Django cuma bisa nge-swap AUTH_USER_MODEL sebelum ada migrasi/data
    user berjalan — ganti belakangan jauh lebih ribet. Jadi app ini
    disiapin dari awal biar ke depannya gampang nambah field lain (role,
    nomor HP, dst) tanpa migrasi ulang yang menyakitkan."""

    full_name = models.CharField("Nama Lengkap", max_length=150, blank=True)
    unit_kerja = models.CharField("Unit Kerja", max_length=100, blank=True)

    # AbstractUser (lewat PermissionsMixin) default-nya pakai
    # related_name="user_set" buat groups & user_permissions — sama
    # persis dengan punya auth.User bawaan Django, yang tetap "ada" di
    # app registry walau udah di-swap. Tanpa override ini, keduanya
    # tabrakan nama reverse accessor (error fields.E304). Pola ini resmi
    # direkomendasikan Django docs buat custom User model.
    groups = models.ManyToManyField(
        Group,
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="accounts_user_set",
        related_query_name="accounts_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="accounts_user_set",
        related_query_name="accounts_user",
    )

    def __str__(self):
        return self.full_name or self.username