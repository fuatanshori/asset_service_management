# equipment/forms.py
from django import forms
from .models import Equipment

INPUT_CLASS = "field-input"


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "name", "brand", "model_type", "serial_number", "acquisition_year",
            "photo", "location_name", "latitude", "longitude", "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "brand": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "model_type": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "serial_number": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "acquisition_year": forms.NumberInput(attrs={"class": INPUT_CLASS}),
            "photo": forms.ClearableFileInput(attrs={"class": INPUT_CLASS}),
            "location_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "cth. Ruang OK 2, Lantai 3"}),
            "latitude": forms.HiddenInput(attrs={"id": "id_latitude"}),
            "longitude": forms.HiddenInput(attrs={"id": "id_longitude"}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }


class EquipmentFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Cari")
    brand = forms.CharField(required=False)
    model_type = forms.CharField(required=False)
    acquisition_year = forms.CharField(required=False)
    status = forms.ChoiceField(required=False, choices=[("", "Semua")] + Equipment.STATUS_CHOICES)