from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from core.widgets import FIELD

from .models import User


class StaffLoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Nom d'utilisateur"),
        widget=forms.TextInput(attrs={"class": FIELD, "autofocus": True}),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD}),
    )


class StaffUserForm(forms.ModelForm):
    """Create/update a staff member; password optional on update."""

    password1 = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD}),
        required=False,
        help_text=_("Laisser vide pour ne pas changer."),
    )
    password2 = forms.CharField(
        label=_("Confirmer le mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD}),
        required=False,
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "phone", "role", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": FIELD}),
            "first_name": forms.TextInput(attrs={"class": FIELD}),
            "last_name": forms.TextInput(attrs={"class": FIELD}),
            "phone": forms.TextInput(attrs={"class": FIELD}),
            "role": forms.Select(attrs={"class": FIELD}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if (p1 or p2) and p1 != p2:
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
