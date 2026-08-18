# equipment/forms.py
from django import forms
from .models import Equipment

INPUT_CLASS = "field-input"


class EquipmentForm(forms.ModelForm):
    """status cuma bisa dipilih manual antara Aktif/Rusak — 2 status
    lainnya (Dijadwalkan, Dalam Perbaikan) murni dikontrol otomatis
    oleh sync_equipment_status() berdasarkan jadwal maintenance yang
    lagi berjalan (app maintenance), jadi sengaja nggak ditawarin
    sebagai pilihan manual di form barang.

    Kalau barang saat ini statusnya Dijadwalkan/Dalam Perbaikan (lagi
    dikontrol jadwal aktif), field status dikunci read-only di sini —
    biar staf yang cuma mau edit field lain (misal notes/foto) nggak
    nggak sengaja "menurunkan" status yang seharusnya dikontrol jadwal.
    """

    class Meta:
        model = Equipment
        fields = [
            "name", "brand", "model_type", "serial_number", "acquisition_year",
            "status", "photo", "location_name", "latitude", "longitude", "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "brand": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "model_type": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "serial_number": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "acquisition_year": forms.NumberInput(attrs={"class": INPUT_CLASS}),
            "status": forms.Select(attrs={"class": INPUT_CLASS}),
            "photo": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
            "location_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "cth. Ruang OK 2, Lantai 3"}),
            "latitude": forms.HiddenInput(attrs={"id": "id_latitude"}),
            "longitude": forms.HiddenInput(attrs={"id": "id_longitude"}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        locked_statuses = (Equipment.STATUS_SCHEDULED, Equipment.STATUS_UNDER_REPAIR)
        if self.instance.pk and self.instance.status in locked_statuses:
            # Lagi dikontrol jadwal aktif — kunci field-nya. Choices
            # dibiarin default (4 pilihan bawaan model) biar nilai
            # "Dijadwalkan"/"Dalam Perbaikan" yang sedang aktif tetap
            # valid buat ditampilkan (cuma nggak bisa diubah).
            self.fields["status"].disabled = True
        else:
            # Barang baru, atau barang yang statusnya nggak lagi
            # dikontrol jadwal — cuma tawarin 2 pilihan manual yang
            # masuk akal.
            self.fields["status"].choices = [
                (Equipment.STATUS_ACTIVE, "Aktif"),
                (Equipment.STATUS_DAMAGED, "Rusak"),
            ]


class EquipmentFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Cari")
    brand = forms.CharField(required=False)
    model_type = forms.CharField(required=False)
    acquisition_year = forms.CharField(required=False)
    status = forms.ChoiceField(required=False, choices=[("", "Semua")] + Equipment.STATUS_CHOICES)


class EquipmentImportForm(forms.Form):
    """Upload file Excel (.xlsx) buat import massal data Equipment.
    Kolom yang dibaca (baris 1 dianggap header, dilewati) lihat
    EQUIPMENT_IMPORT_HEADERS di equipment_import view (views.py) buat
    detail parsing-nya."""

    file = forms.FileField(
        label="File Excel (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"class": INPUT_CLASS, "accept": ".xlsx"}),
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if not file.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("File harus berformat .xlsx (Excel).")
        return file