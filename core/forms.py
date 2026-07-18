from django import forms
from django.utils.translation import gettext_lazy as _

from core.widgets import FIELD, FILE

from .models import ContactMessage, Restaurant

# Curated palettes for one-click branding (senior UX: don't force hex for everyone)
COLOR_PRESETS = [
    {
        "id": "orange_noir",
        "label": _("Orange & Noir"),
        "ink": "#0A0A0A",
        "paper": "#F4F4F5",
        "surface": "#FFFFFF",
        "accent": "#FF5A00",
        "accent_dark": "#E04E00",
    },
    {
        "id": "ember",
        "label": _("Braise"),
        "ink": "#121212",
        "paper": "#E8E6E1",
        "surface": "#F7F6F3",
        "accent": "#C2410C",
        "accent_dark": "#9A3412",
    },
    {
        "id": "forest",
        "label": _("Forêt"),
        "ink": "#14291F",
        "paper": "#E7EDE7",
        "surface": "#F3F7F3",
        "accent": "#2F6B4F",
        "accent_dark": "#1D4A36",
    },
    {
        "id": "ocean",
        "label": _("Océan"),
        "ink": "#0F1C24",
        "paper": "#E6EBEE",
        "surface": "#F2F5F7",
        "accent": "#0E7490",
        "accent_dark": "#155E75",
    },
    {
        "id": "wine",
        "label": _("Vin"),
        "ink": "#1A1214",
        "paper": "#F0E8E6",
        "surface": "#F8F3F1",
        "accent": "#9F1239",
        "accent_dark": "#881337",
    },
]


COLOR_INPUT = (
    "h-11 w-14 cursor-pointer rounded-md border border-stone-300 bg-white p-1 "
    "outline-none focus:border-vermilion focus:ring-2 focus:ring-vermilion/20"
)


class RestaurantForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = [
            "name",
            "description_fr",
            "description_en",
            "address",
            "phone",
            "email",
            "opening_hours_fr",
            "opening_hours_en",
            "logo",
            "logo_url",
            "cover_image",
            "cover_image_url",
            "color_ink",
            "color_paper",
            "color_surface",
            "color_accent",
            "color_accent_dark",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": FIELD}),
            "description_fr": forms.Textarea(attrs={"class": FIELD, "rows": 4}),
            "description_en": forms.Textarea(attrs={"class": FIELD, "rows": 4}),
            "address": forms.TextInput(attrs={"class": FIELD}),
            "phone": forms.TextInput(attrs={"class": FIELD}),
            "email": forms.EmailInput(attrs={"class": FIELD}),
            "opening_hours_fr": forms.Textarea(attrs={"class": FIELD, "rows": 3}),
            "opening_hours_en": forms.Textarea(attrs={"class": FIELD, "rows": 3}),
            "logo": forms.FileInput(
                attrs={"class": FILE, "accept": "image/*"}
            ),
            "logo_url": forms.URLInput(
                attrs={"class": FIELD, "placeholder": "https://…", "inputmode": "url"}
            ),
            "cover_image": forms.FileInput(
                attrs={"class": FILE, "accept": "image/*"}
            ),
            "cover_image_url": forms.URLInput(
                attrs={"class": FIELD, "placeholder": "https://…", "inputmode": "url"}
            ),
            "color_ink": forms.TextInput(attrs={"class": COLOR_INPUT, "type": "color"}),
            "color_paper": forms.TextInput(attrs={"class": COLOR_INPUT, "type": "color"}),
            "color_surface": forms.TextInput(attrs={"class": COLOR_INPUT, "type": "color"}),
            "color_accent": forms.TextInput(attrs={"class": COLOR_INPUT, "type": "color"}),
            "color_accent_dark": forms.TextInput(attrs={"class": COLOR_INPUT, "type": "color"}),
        }
        help_texts = {
            "logo": _("Fichier local ou photo (prioritaire)."),
            "logo_url": _("Sinon, lien URL du logo."),
            "cover_image": _("Fichier local ou photo (prioritaire)."),
            "cover_image_url": _("Sinon, lien URL de la couverture."),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": FIELD, "placeholder": _("Votre nom"), "autocomplete": "name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": FIELD, "placeholder": "vous@email.com", "autocomplete": "email"}
            ),
            "phone": forms.TextInput(
                attrs={"class": FIELD, "type": "tel", "placeholder": "+243 …", "autocomplete": "tel"}
            ),
            "subject": forms.TextInput(
                attrs={"class": FIELD, "placeholder": _("Sujet de votre message")}
            ),
            "message": forms.Textarea(
                attrs={"class": FIELD, "rows": 5, "placeholder": _("Écrivez votre message…")}
            ),
        }
