from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.permissions import serveur_or_admin

from .forms import ReservationForm, StaffReservationForm
from .models import Reservation


def reservation_create(request):
    """Public reservation request form."""
    form = ReservationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return render(request, "reservations/thanks.html")
    return render(request, "reservations/form.html", {"form": form})


@serveur_or_admin
def staff_reservations(request):
    status = request.GET.get("status", "")
    reservations = Reservation.objects.all()
    if status:
        reservations = reservations.filter(status=status)
    return render(
        request,
        "reservations/staff_list.html",
        {
            "reservations": reservations,
            "current_status": status,
            "statuses": Reservation.Status.choices,
        },
    )


@serveur_or_admin
def staff_reservation_create(request):
    form = StaffReservationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Réservation créée."))
        return redirect("reservations:staff_list")
    return render(
        request,
        "reservations/staff_form.html",
        {"form": form, "title": _("Nouvelle réservation")},
    )


@serveur_or_admin
def staff_reservation_update(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    form = StaffReservationForm(request.POST or None, instance=reservation)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Réservation mise à jour."))
        return redirect("reservations:staff_list")
    return render(
        request,
        "reservations/staff_form.html",
        {
            "form": form,
            "title": _("Modifier — %(name)s") % {"name": reservation.name},
        },
    )


@serveur_or_admin
def staff_reservation_delete(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    if request.method == "POST":
        name = reservation.name
        reservation.delete()
        messages.success(request, _("Réservation de %(name)s supprimée.") % {"name": name})
        return redirect("reservations:staff_list")
    return render(
        request,
        "reservations/staff_confirm_delete.html",
        {"reservation": reservation},
    )


@serveur_or_admin
@require_POST
def staff_reservation_set_status(request, pk, status):
    reservation = get_object_or_404(Reservation, pk=pk)
    valid = {s.value for s in Reservation.Status}
    if status in valid:
        reservation.status = status
        reservation.save(update_fields=["status"])
        messages.success(
            request,
            _("Réservation de %(name)s : %(status)s.")
            % {"name": reservation.name, "status": reservation.get_status_display()},
        )
    return redirect("reservations:staff_list")
