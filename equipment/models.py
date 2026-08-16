# equipment/models.py

from django.db import models
from django.urls import reverse


class Equipment(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_SCHEDULED = "scheduled"
    STATUS_UNDER_REPAIR = "under_repair"
    STATUS_DAMAGED = "damaged"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Aktif"),
        (STATUS_SCHEDULED, "Dijadwalkan"),
        (STATUS_UNDER_REPAIR, "Dalam Perbaikan"),
        (STATUS_DAMAGED, "Rusak"),
    ]

    serial_number = models.CharField("Nomor Seri", max_length=100, unique=True)
    name = models.CharField("Nama Barang", max_length=150)
    brand = models.CharField("Merk", max_length=100)
    model_type = models.CharField("Tipe", max_length=100, blank=True)
    acquisition_year = models.PositiveIntegerField("Tahun Perolehan")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField("Keterangan", blank=True)
    photo = models.ImageField("Foto Barang", upload_to="equipment_photos/", blank=True, null=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    location_name = models.CharField("Lokasi", max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    def get_absolute_url(self):
        return reverse("equipment_detail", args=[self.pk])

    @property
    def status_color(self):
        return {
            self.STATUS_ACTIVE: "green",
            self.STATUS_SCHEDULED: "brand",
            self.STATUS_UNDER_REPAIR: "amber",
            self.STATUS_DAMAGED: "red",
        }.get(self.status, "muted")

    @property
    def needs_repair_schedule(self):
        return self.status != self.STATUS_ACTIVE

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None