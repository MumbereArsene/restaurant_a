from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.widgets import FIELD

from .models import Reservation


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["name", "phone", "date", "time", "guests", "notes"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": FIELD,
                    "placeholder": _("Nom complet"),
                    "autocomplete": "name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": FIELD,
                    "type": "tel",
                    "placeholder": "+243 …",
                    "autocomplete": "tel",
                }
            ),
            "date": forms.DateInput(attrs={"class": FIELD, "type": "date"}),
            "time": forms.TimeInput(attrs={"class": FIELD, "type": "time"}),
            "guests": forms.NumberInput(
                attrs={"class": FIELD, "min": 1, "max": 50, "placeholder": "2"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": FIELD,
                    "rows": 3,
                    "placeholder": _("Allergie, anniversaire, préférences…"),
                }
            ),
        }

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date < timezone.localdate():
            raise forms.ValidationError(_("La date ne peut pas être dans le passé."))
        return date


class StaffReservationForm(forms.ModelForm):
    """Staff can create/edit including status; past dates allowed for corrections."""

    class Meta:
        model = Reservation
        fields = ["name", "phone", "date", "time", "guests", "notes", "status"]
        widgets = {
            "name": forms.TextInput(attrs={"class": FIELD}),
            "phone": forms.TextInput(attrs={"class": FIELD, "type": "tel"}),
            "date": forms.DateInput(attrs={"class": FIELD, "type": "date"}),
            "time": forms.TimeInput(attrs={"class": FIELD, "type": "time"}),
            "guests": forms.NumberInput(attrs={"class": FIELD, "min": 1, "max": 50}),
            "notes": forms.Textarea(attrs={"class": FIELD, "rows": 3}),
            "status": forms.Select(attrs={"class": FIELD}),
        }
