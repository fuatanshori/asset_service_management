from django import forms

from equipment.models import Equipment
from .models import MaintenanceLog, MaintenanceSchedule

INPUT_CLASS = "field-input"


class MaintenanceScheduleForm(forms.ModelForm):
    """Add/edit form for MaintenanceSchedule.

    `equipment` is rendered as a HiddenInput because the template pairs
    it with a JS search-as-you-type picker (see equipment_search view in
    the equipment app) rather than a plain <select>.

    Equipment is intentionally LOCKED (disabled) once a schedule already
    exists (edit mode) — see __init__ below.
    """

    class Meta:
        model = MaintenanceSchedule
        fields = ["equipment", "scheduled_date", "maintenance_type", "notes"]
        widgets = {
            "equipment": forms.HiddenInput(attrs={"id": "id_equipment"}),
            "scheduled_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}),
            "maintenance_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Barang pada jadwal yang SUDAH ADA tidak boleh diganti lewat
            # edit — cuma bisa dipilih pas bikin jadwal baru. Alasannya:
            # (1) riwayat (teknisi/biaya/foto) yang sudah tercatat jadi
            # rancu kalau barangnya diganti belakangan, dan (2)
            # sync_equipment_status() cuma re-check status barang kalau
            # scheduled_date/maintenance_type berubah — bukan kalau
            # equipment-nya sendiri yang berubah, jadi status barang lama
            # maupun baru bisa nyangkut salah kalau field ini dibiarkan
            # bebas diedit. `disabled=True` di sini mengunci di level
            # Django form — POST yang mencoba mengubahnya tetap diabaikan,
            # bukan cuma dikunci secara visual di template.
            self.fields["equipment"].disabled = True

    def clean_equipment(self):
        """Block scheduling a new maintenance event for equipment that's
        already mid-schedule (status "scheduled" or "under_repair") —
        prevents double-booking. Only applies to NEW schedules."""
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
    """Non-model filter form for the schedule list view."""

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
    """Edit form for a MaintenanceLog. There is no "add" counterpart —
    every log is created automatically alongside its schedule. `schedule`
    is intentionally excluded from `fields`.

    The `result` field is disabled (read-only) when this log is not the
    equipment's latest — everything else stays freely editable. This
    only prevents accidentally re-flagging old, already-resolved work as
    "in progress" again; it does not protect equipment.status by itself
    (that's handled independently by sync_equipment_status() in
    models.py, which always reads from the latest schedule regardless).
    """

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.instance.is_editable:
            self.fields["result"].disabled = True


class LogFilterForm(forms.Form):
    """Non-model filter form for the log (riwayat) list view."""

    q = forms.CharField(required=False, label="Cari")
    result = forms.ChoiceField(required=False, choices=[("", "Semua")] + MaintenanceLog.RESULT_CHOICES)
    year = forms.CharField(required=False)