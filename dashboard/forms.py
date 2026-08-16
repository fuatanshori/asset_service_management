#dashboard/forms.py
from django import forms

LIMIT_CHOICES = [("5", "Top 5"), ("10", "Top 10"), ("20", "Top 20")]

INPUT_CLASS = "field-input"


class WidgetDateFilterForm(forms.Form):
    """Form generik: dipakai berkali-kali di dashboard dengan `prefix`
    beda-beda (cost, type, result, dst) supaya tiap kartu punya filter
    sendiri di GET params tanpa tabrakan nama field."""
    date_from = forms.DateField(
        required=False, label="Dari",
        widget=forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}),
    )
    date_to = forms.DateField(
        required=False, label="Sampai",
        widget=forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}),
    )


class WidgetRankingFilterForm(WidgetDateFilterForm):
    limit = forms.ChoiceField(
        required=False, label="Tampilkan", choices=LIMIT_CHOICES, initial="5",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )