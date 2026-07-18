from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from .forms import StaffLoginForm, StaffUserForm
from .models import User
from .permissions import personnel_required


class StaffLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = StaffLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        """Role-based landing after login."""
        user = self.request.user
        if user.is_admin_role or user.is_manager_role:
            return reverse("core:dashboard")
        if user.is_caissier_role:
            return reverse("cash:ledger")
        if user.is_serveur_role:
            return reverse("tables:serveur_home")
        if user.is_cuisine_role:
            return reverse("orders:staff_list")
        return reverse("core:dashboard")


class StaffLogoutView(auth_views.LogoutView):
    next_page = "accounts:login"


@personnel_required
def personnel_list(request):
    users = User.objects.order_by("role", "username")
    return render(request, "accounts/personnel_list.html", {"users": users})


@personnel_required
def personnel_create(request):
    form = StaffUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, _("Compte « %(name)s » créé.") % {"name": user.username})
        return redirect("accounts:personnel_list")
    return render(
        request,
        "accounts/personnel_form.html",
        {"form": form, "title": _("Nouveau membre du personnel")},
    )


@personnel_required
def personnel_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = StaffUserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Compte « %(name)s » mis à jour.") % {"name": user.username})
        return redirect("accounts:personnel_list")
    return render(
        request,
        "accounts/personnel_form.html",
        {"form": form, "title": _("Modifier %(name)s") % {"name": user.username}},
    )


@personnel_required
def personnel_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, _("Vous ne pouvez pas supprimer votre propre compte."))
        return redirect("accounts:personnel_list")
    if request.method == "POST":
        username = user.username
        user.delete()
        messages.success(request, _("Compte « %(name)s » supprimé.") % {"name": username})
        return redirect("accounts:personnel_list")
    return render(request, "accounts/personnel_confirm_delete.html", {"user_obj": user})
