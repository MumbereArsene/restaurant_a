from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.utils.translation import gettext_lazy as _

from core.widgets import FIELD

from .models import User


class ClientRegisterForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": FIELD, "autocomplete": "email"}),
    )
    phone = forms.CharField(
        label=_("WhatsApp (optionnel)"),
        required=False,
        widget=forms.TextInput(
            attrs={"class": FIELD, "autocomplete": "tel", "placeholder": "+243 …"}
        ),
    )
    password1 = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD, "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label=_("Confirmer le mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD, "autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cet email."))
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        user = User(
            username=email,
            email=email,
            phone=(self.cleaned_data.get("phone") or "").strip(),
            role=User.Role.CLIENT,
        )
        user.set_password(self.cleaned_data["password1"])
        user.save()
        return user


class StaffLoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Nom d'utilisateur"),
        widget=forms.TextInput(attrs={"class": FIELD, "autofocus": True}),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if getattr(user, "is_client_role", False):
            raise forms.ValidationError(
                _("Ce compte est un espace client. Utilisez la connexion client."),
                code="client_account",
            )


class ClientLoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": FIELD, "autofocus": True, "autocomplete": "email"}),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": FIELD}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not getattr(user, "is_client_role", False):
            raise forms.ValidationError(
                _("Utilisez la connexion personnel pour ce compte."),
                code="staff_account",
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
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": FIELD}),
            "first_name": forms.TextInput(attrs={"class": FIELD}),
            "last_name": forms.TextInput(attrs={"class": FIELD}),
            "email": forms.EmailInput(attrs={"class": FIELD, "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"class": FIELD}),
            "role": forms.Select(attrs={"class": FIELD}),
        }

    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        allowed = User.assignable_staff_roles(actor)
        self.fields["role"].choices = [c for c in User.Role.choices if c[0] in allowed]
        self.fields["email"].required = False
        if self.instance.pk is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean_role(self):
        role = self.cleaned_data.get("role")
        allowed = User.assignable_staff_roles(self.actor)
        if role not in allowed:
            raise forms.ValidationError(_("Vous n'avez pas le droit d'attribuer ce rôle."))
        return role

    def clean_is_active(self):
        is_active = self.cleaned_data.get("is_active")
        if (
            self.instance.pk
            and not is_active
            and self.instance.is_protected_last_admin()
        ):
            raise forms.ValidationError(
                _("Impossible de désactiver le dernier administrateur.")
            )
        return is_active

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if (p1 or p2) and p1 != p2:
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        if p1:
            try:
                password_validation.validate_password(p1, self.instance)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        role = cleaned.get("role")
        if (
            self.instance.pk
            and self.instance.is_protected_last_admin()
            and role
            and role != User.Role.ADMIN
            and not self.instance.is_superuser
        ):
            self.add_error(
                "role",
                _("Impossible de retirer le rôle admin du dernier administrateur."),
            )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": FIELD, "autocomplete": "email"}
        )


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {"class": FIELD, "autocomplete": "new-password"}
        )
        self.fields["new_password2"].widget.attrs.update(
            {"class": FIELD, "autocomplete": "new-password"}
        )
