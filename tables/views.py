import io

import qrcode
from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.permissions import admin_required, serveur_or_admin, staff_any
from core.widgets import FIELD

from .models import Table


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ["number", "capacity", "status"]
        widgets = {
            "number": forms.NumberInput(attrs={"class": FIELD, "min": 1}),
            "capacity": forms.NumberInput(attrs={"class": FIELD, "min": 1}),
            "status": forms.Select(attrs={"class": FIELD}),
        }


@staff_any
def table_list(request):
    tables = Table.objects.all()
    return render(request, "tables/table_list.html", {"tables": tables})


@admin_required
def table_create(request):
    form = TableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        table = form.save()
        messages.success(request, _("Table %(n)s créée avec son QR code.") % {"n": table.number})
        return redirect("tables:list")
    return render(
        request, "tables/table_form.html", {"form": form, "title": _("Nouvelle table")}
    )


@admin_required
def table_update(request, pk):
    table = get_object_or_404(Table, pk=pk)
    form = TableForm(request.POST or None, instance=table)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Table %(n)s mise à jour.") % {"n": table.number})
        return redirect("tables:list")
    return render(
        request,
        "tables/table_form.html",
        {"form": form, "title": _("Modifier la table %(n)s") % {"n": table.number}},
    )


@admin_required
def table_delete(request, pk):
    from django.db.models.deletion import ProtectedError

    table = get_object_or_404(Table, pk=pk)
    orders_count = table.orders.count()

    if request.method == "POST":
        number = table.number
        try:
            table.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "Impossible de supprimer la table %(n)s : des commandes y sont liées. "
                    "Libérez ou conservez l’historique des commandes."
                )
                % {"n": number},
            )
            return redirect("tables:list")
        messages.success(request, _("Table %(n)s supprimée.") % {"n": number})
        return redirect("tables:list")

    return render(
        request,
        "tables/table_confirm_delete.html",
        {"table": table, "orders_count": orders_count},
    )


@admin_required
def table_regenerate_token(request, pk):
    table = get_object_or_404(Table, pk=pk)
    if request.method == "POST":
        table.regenerate_token()
        messages.success(
            request,
            _("Nouveau QR généré pour la table %(n)s. L'ancien code est invalide.")
            % {"n": table.number},
        )
    return redirect("tables:qr_view", pk=table.pk)


@staff_any
def table_qr_view(request, pk):
    """Printable page showing the QR code and its target URL."""
    table = get_object_or_404(Table, pk=pk)
    return render(
        request,
        "tables/table_qr.html",
        {"table": table, "order_url": table.order_url(request)},
    )


@staff_any
def table_qr_png(request, pk):
    """Serve the QR code image (used for display and download)."""
    table = get_object_or_404(Table, pk=pk)
    img = qrcode.make(table.order_url(request), box_size=12, border=2)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    if request.GET.get("download"):
        response["Content-Disposition"] = f'attachment; filename="table-{table.number}-qr.png"'
    return response


def _extract_table_token(raw: str) -> str:
    text = (raw or "").strip()
    if "/order/" in text:
        part = text.split("/order/")[-1]
        return part.split("/")[0].split("?")[0].strip()
    return text


@serveur_or_admin
def serveur_home(request):
    """Floor hub: live orders, invoice scan, room board."""
    from orders.models import Order

    tables = list(Table.objects.all())
    busy_count = sum(1 for t in tables if t.status == Table.Status.OCCUPEE)
    free_count = len(tables) - busy_count
    open_qs = Order.objects.filter(
        status__in=[
            Order.Status.EN_ATTENTE,
            Order.Status.ACCEPTEE,
            Order.Status.EN_PREPARATION,
            Order.Status.PRETE,
            Order.Status.SERVIE,
        ]
    )
    context = {
        "tables": tables,
        "busy_count": busy_count,
        "free_count": free_count,
        "orders": open_qs.select_related("table", "customer").prefetch_related("items__dish")[:50],
        "open_count": open_qs.count(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "orders/partials/serveur_order_list.html", context)
    return render(request, "tables/serveur_home.html", context)


@serveur_or_admin
def table_free_scan(request):
    """Alias historique → espace serveur."""
    return redirect("tables:serveur_home")


@serveur_or_admin
@require_POST
def table_free_by_token(request):
    """Free a table after serveur/admin scans its QR (or enters the token)."""
    from django.http import JsonResponse
    from django.urls import reverse

    token = _extract_table_token(request.POST.get("token", ""))
    table = Table.objects.filter(qr_token=token).first()
    wants_json = (
        request.headers.get("HX-Request")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

    if not table:
        msg = _("QR invalide. Scannez le QR de la table.")
        if wants_json:
            return JsonResponse({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("tables:serveur_home")

    was_busy = table.status == Table.Status.OCCUPEE
    if table.has_open_orders():
        msg = _(
            "Des commandes sont encore en cours sur la table %(n)s. "
            "Annulez-les ou encaissez-les avant de libérer."
        ) % {"n": table.number}
        if wants_json:
            return JsonResponse({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("tables:serveur_home")

    table.status = Table.Status.LIBRE
    table.save(update_fields=["status"])

    from core.audit import log_action

    log_action(
        request.user,
        "table.free",
        _("Table %(n)s libérée (scan)") % {"n": table.number},
        object_type="Table",
        object_id=table.pk,
    )

    if was_busy:
        msg = _("Table %(n)s libérée.") % {"n": table.number}
    else:
        msg = _("Table %(n)s était déjà libre.") % {"n": table.number}

    home = reverse("tables:serveur_home") + f"?ok=1&table={table.number}"
    if wants_json:
        return JsonResponse(
            {
                "ok": True,
                "message": msg,
                "table": table.number,
                "redirect": home,
            }
        )
    messages.success(request, msg)
    return redirect(home)


@serveur_or_admin
def table_free_confirm(request, token):
    """Landing when a logged-in serveur opens the physical table QR."""
    table = get_object_or_404(Table, qr_token=token)
    return render(request, "tables/free_confirm.html", {"table": table})


@serveur_or_admin
@require_POST
def table_free_by_pk(request, pk):
    from core.audit import log_action

    table = get_object_or_404(Table, pk=pk)
    if table.has_open_orders():
        messages.error(
            request,
            _(
                "Des commandes sont encore en cours sur la table %(n)s. "
                "Annulez-les ou encaissez-les avant de libérer."
            )
            % {"n": table.number},
        )
        next_url = request.POST.get("next") or "tables:serveur_home"
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect("tables:serveur_home")
    table.status = Table.Status.LIBRE
    table.save(update_fields=["status"])
    log_action(
        request.user,
        "table.free",
        _("Table %(n)s libérée") % {"n": table.number},
        object_type="Table",
        object_id=table.pk,
    )
    messages.success(request, _("Table %(n)s libérée.") % {"n": table.number})
    next_url = request.POST.get("next") or "tables:serveur_home"
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(next_url)
