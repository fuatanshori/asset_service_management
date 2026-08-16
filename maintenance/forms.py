#maintenance/forms.py

from django import forms
from equipment.models import Equipment
from .models import MaintenanceLog, MaintenanceSchedule

INPUT_CLASS = "field-input"


class MaintenanceScheduleForm(forms.ModelForm):
    class Meta:
        model = MaintenanceSchedule
        fields = ["equipment", "scheduled_date", "maintenance_type", "notes"]
        widgets = {
            "equipment": forms.HiddenInput(attrs={"id": "id_equipment"}),
            "scheduled_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "maintenance_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and not self.instance.is_editable:
            raise forms.ValidationError(
                "Jadwal ini bukan jadwal terbaru untuk barang ini — sudah menjadi arsip, tidak bisa diedit."
            )
        return cleaned_data

    def clean_equipment(self):
        equipment = self.cleaned_data.get("equipment")
        if not self.instance.pk and equipment and equipment.status in (
            Equipment.STATUS_UNDER_REPAIR, Equipment.STATUS_SCHEDULED
        ):
            raise forms.ValidationError(
                'Barang "%s" sedang berstatus "%s" — tidak bisa ditambahkan jadwal baru '
                "sampai jadwal yang berjalan selesai atau dihapus."
                % (equipment.name, equipment.get_status_display())
            )
        return equipment


class ScheduleFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Cari")
    maintenance_type = forms.ChoiceField(
        required=False, choices=[("", "Semua")] + MaintenanceSchedule.TYPE_CHOICES
    )
    result = forms.ChoiceField(
        required=False, choices=[("", "Semua")] + MaintenanceLog.RESULT_CHOICES
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


class MaintenanceLogForm(forms.ModelForm):
    """Ngedit riwayat (1:1) milik sebuah schedule — schedule-nya sendiri
    gak bisa diganti dari sini, implisit dari mana form ini dipanggil."""
    class Meta:
        model = MaintenanceLog
        fields = [
            "date", "technician", "action_taken", "result", "cost", "completed_date",
            "photo_before", "photo_after", "photo_receipt",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "technician": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "action_taken": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "result": forms.Select(attrs={"class": INPUT_CLASS, "id": "id_result"}),
            "cost": forms.NumberInput(attrs={"class": INPUT_CLASS}),
            "completed_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date", "id": "id_completed_date"}),
            "photo_before": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
            "photo_after": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
            "photo_receipt": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and not self.instance.is_editable:
            raise forms.ValidationError(
                "Riwayat ini bukan riwayat terbaru untuk barang ini — sudah menjadi arsip, tidak bisa diedit."
            )
        return cleaned_data


class LogFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Cari")
    result = forms.ChoiceField(required=False, choices=[("", "Semua")] + MaintenanceLog.RESULT_CHOICES)
    year = forms.CharField(required=False)