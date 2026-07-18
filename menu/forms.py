from django import forms
from django.utils.translation import gettext_lazy as _

from core.widgets import FIELD, FILE

from .models import Category, Dish


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name_fr", "name_en", "position", "is_active"]
        widgets = {
            "name_fr": forms.TextInput(attrs={"class": FIELD}),
            "name_en": forms.TextInput(attrs={"class": FIELD}),
            "position": forms.NumberInput(attrs={"class": FIELD, "min": 0}),
        }


class DishForm(forms.ModelForm):
    clear_image = forms.BooleanField(
        required=False,
        label=_("Supprimer l'image uploadée"),
    )

    class Meta:
        model = Dish
        fields = [
            "category",
            "name_fr",
            "name_en",
            "description_fr",
            "description_en",
            "price",
            "image",
            "image_url",
            "is_active",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": FIELD}),
            "name_fr": forms.TextInput(attrs={"class": FIELD}),
            "name_en": forms.TextInput(attrs={"class": FIELD}),
            "description_fr": forms.Textarea(attrs={"class": FIELD, "rows": 3}),
            "description_en": forms.Textarea(attrs={"class": FIELD, "rows": 3}),
            "price": forms.NumberInput(attrs={"class": FIELD, "min": 0, "step": "0.01"}),
            "image": forms.FileInput(
                attrs={
                    "class": FILE,
                    "accept": "image/*",
                }
            ),
            "image_url": forms.URLInput(
                attrs={
                    "class": FIELD,
                    "placeholder": "https://…",
                    "inputmode": "url",
                }
            ),
        }
        help_texts = {
            "image": _("Depuis votre téléphone ou ordinateur (galerie / caméra)."),
            "image_url": _("Ou collez un lien image (https://…). Priorité au fichier uploadé."),
        }

    def save(self, commit=True):
        dish = super().save(commit=False)
        if self.cleaned_data.get("clear_image") and dish.image:
            dish.image.delete(save=False)
            dish.image = None
        if commit:
            dish.save()
        return dish
