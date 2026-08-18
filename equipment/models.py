# equipment/models.py

from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
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

    # unique=True + null=True (bukan cuma blank=True) SENGAJA dipasang
    # bareng — biar banyak barang boleh sama-sama nggak punya nomor seri
    # (misal data lama dari Excel yang datanya nggak lengkap) tanpa
    # nabrak constraint unique. Di SQL, banyak baris boleh sama-sama
    # NULL tanpa dianggap "sama"; beda kalau dikasih string kosong ""
    # (itu tetap dianggap 1 nilai yang harus unik, jadi cuma 1 barang
    # yang bisa punya serial number kosong kalau nggak pakai null=True).
    serial_number = models.CharField("Nomor Seri", max_length=100, null=True, blank=True)
    name = models.CharField("Nama Barang", max_length=150)
    brand = models.CharField("Merk", max_length=100, blank=True)
    model_type = models.CharField("Tipe", max_length=100, blank=True)
    acquisition_year = models.PositiveIntegerField("Tahun Perolehan", null=True, blank=True)
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
        if self.serial_number:
            return f"{self.name} ({self.serial_number})"
        return self.name

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

    def save(self, *args, **kwargs):
        """Kalau foto diganti dengan file baru, atau dihapus lewat
        checkbox "Clear" di form — file fisik yang LAMA dihapus dari
        disk juga, biar nggak numpuk jadi sampah yang nggak kepakai.
        Cuma jalan kalau foto beneran berubah; kalau form disave tanpa
        nyentuh field foto, file lama dibiarkan apa adanya."""
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values("photo").first()
            if old and old["photo"] and old["photo"] != self.photo.name:
                self.photo.storage.delete(old["photo"])
        super().save(*args, **kwargs)


@receiver(pre_delete, sender=Equipment)
def delete_equipment_photo_file(sender, instance, **kwargs):
    """Hapus file foto fisik dari disk pas record Equipment-nya
    dihapus. Pakai signal pre_delete (bukan override delete()) karena
    Django tidak memanggil delete() per-instance untuk objek yang
    kehapus lewat cascade delete — cuma signal pre_delete/post_delete
    yang reliably jalan di semua kasus."""
    if instance.photo:
        instance.photo.storage.delete(instance.photo.name)