from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _

from core.audit import log_action

from .forms import (
    ClientLoginForm,
    ClientRegisterForm,
    StaffLoginForm,
    StaffUserForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .models import User
from .permissions import can_manage_staff_user, personnel_required


class StaffLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = StaffLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        """Role-based landing after login."""
        user = self.request.user
        if user.is_client_role:
            return reverse("orders:client_invoices")
        if user.is_admin_role or user.is_manager_role:
            return reverse("core:dashboard")
        if user.is_caissier_role:
            return reverse("cash:ledger")
        if user.is_serveur_role:
            return reverse("tables:serveur_home")
        if user.is_cuisine_role:
            return reverse("orders:staff_list")
        return reverse("core:dashboard")


class ClientLoginView(auth_views.LoginView):
    template_name = "accounts/client_login.html"
    authentication_form = ClientLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("orders:client_invoices")


class ClientLogoutView(auth_views.LogoutView):
    next_page = "accounts:client_login"


def client_register(request):
    if request.user.is_authenticated and request.user.is_client_role:
        return redirect("orders:client_invoices")
    form = ClientRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, _("Compte créé. Vos factures apparaîtront ici."))
        return redirect("orders:client_invoices")
    return render(request, "accounts/client_register.html", {"form": form})


class StaffLogoutView(auth_views.LogoutView):
    next_page = "accounts:login"


def _staff_user_qs():
    return User.objects.exclude(role=User.Role.CLIENT)


def _require_manageable(request, target: User) -> None:
    if not can_manage_staff_user(request.user, target):
        raise PermissionDenied


class StaffPasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")
    extra_email_context = {"reset_kind": "staff"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reset_kind"] = "staff"
        ctx["login_url"] = reverse("accounts:login")
        return ctx


class ClientPasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:client_password_reset_done")
    extra_email_context = {"reset_kind": "client"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reset_kind"] = "client"
        ctx["login_url"] = reverse("accounts:client_login")
        return ctx


class StaffPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["login_url"] = reverse("accounts:login")
        return ctx


class ClientPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["login_url"] = reverse("accounts:client_login")
        return ctx


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


@personnel_required
def personnel_list(request):
    users = _staff_user_qs().order_by("role", "username")
    return render(request, "accounts/personnel_list.html", {"users": users})


@personnel_required
def personnel_create(request):
    form = StaffUserForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_action(
            request.user,
            "personnel.create",
            _("Compte « %(name)s » créé (rôle %(role)s)")
            % {"name": user.username, "role": user.get_role_display()},
            object_type="User",
            object_id=user.pk,
        )
        messages.success(request, _("Compte « %(name)s » créé.") % {"name": user.username})
        return redirect("accounts:personnel_list")
    return render(
        request,
        "accounts/personnel_form.html",
        {"form": form, "title": _("Nouveau membre du personnel")},
    )


@personnel_required
def personnel_update(request, pk):
    user = get_object_or_404(_staff_user_qs(), pk=pk)
    _require_manageable(request, user)
    before_role = user.role
    before_active = user.is_active
    form = StaffUserForm(request.POST or None, instance=user, actor=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        user.refresh_from_db()
        log_action(
            request.user,
            "personnel.update",
            _(
                "Compte « %(name)s » modifié (rôle %(before)s → %(after)s, "
                "actif %(ba)s → %(aa)s)"
            )
            % {
                "name": user.username,
                "before": before_role,
                "after": user.role,
                "ba": before_active,
                "aa": user.is_active,
            },
            object_type="User",
            object_id=user.pk,
        )
        messages.success(request, _("Compte « %(name)s » mis à jour.") % {"name": user.username})
        return redirect("accounts:personnel_list")
    return render(
        request,
        "accounts/personnel_form.html",
        {"form": form, "title": _("Modifier %(name)s") % {"name": user.username}},
    )


@personnel_required
def personnel_delete(request, pk):
    user = get_object_or_404(_staff_user_qs(), pk=pk)
    _require_manageable(request, user)
    if user == request.user:
        messages.error(request, _("Vous ne pouvez pas supprimer votre propre compte."))
        return redirect("accounts:personnel_list")
    if user.is_protected_last_admin():
        messages.error(request, _("Impossible de supprimer le dernier administrateur."))
        return redirect("accounts:personnel_list")
    if request.method == "POST":
        username = user.username
        user_pk = user.pk
        user.delete()
        log_action(
            request.user,
            "personnel.delete",
            _("Compte « %(name)s » supprimé") % {"name": username},
            object_type="User",
            object_id=user_pk,
        )
        messages.success(request, _("Compte « %(name)s » supprimé.") % {"name": username})
        return redirect("accounts:personnel_list")
    return render(request, "accounts/personnel_confirm_delete.html", {"user_obj": user})
