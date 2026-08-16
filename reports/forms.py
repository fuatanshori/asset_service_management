# reports/forms.py
from django import forms

INPUT_CLASS = "field-input"


class ReportFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False, label="Dari Tanggal",
        widget=forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}),
    )
    date_to = forms.DateField(
        required=False, label="Sampai Tanggal",
        widget=forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}),
    )