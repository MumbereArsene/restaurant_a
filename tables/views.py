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
        messages.success(
            request,
            _("Table %(n)s créée — code %(code)s.")
            % {"n": table.number, "code": table.public_code},
        )
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
            _("Nouveau code %(code)s pour la table %(n)s. L'ancien code est invalide.")
            % {"code": table.public_code, "n": table.number},
        )
    return redirect("tables:qr_view", pk=table.pk)


@staff_any
def table_qr_view(request, pk):
    """Printable card with the public table code."""
    table = get_object_or_404(Table, pk=pk)
    return render(request, "tables/table_qr.html", {"table": table})


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
    from .codes import extract_raw_code, normalize_code

    text = extract_raw_code(raw)
    return normalize_code(text) or text


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
    """Free a table after the waiter enters its public code."""
    from django.http import JsonResponse
    from django.urls import reverse

    token = request.POST.get("token", "")
    from .codes import resolve_table

    table = resolve_table(token)
    wants_json = (
        request.headers.get("HX-Request")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )

    if not table:
        msg = _("Code table invalide.")
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
        _("Table %(n)s libérée (code %(code)s)")
        % {"n": table.number, "code": table.public_code},
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
    """Landing when a logged-in serveur looks up a table code."""
    from .codes import resolve_table

    table = resolve_table(token)
    if not table:
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


@serveur_or_admin
def staff_code_lookup(request):
    """Waiter types a table code or invoice code → pay, free, or error."""
    from django.urls import reverse

    from orders.models import Order

    from .codes import resolve_order_by_code, resolve_table

    raw = request.POST.get("code") or request.GET.get("code") or ""
    release = request.POST.get("release") or request.GET.get("release") or "1"
    if release not in ("0", "1"):
        release = "1"

    order = resolve_order_by_code(raw)
    table = resolve_table(raw) if not order else order.table

    if order:
        if order.status == Order.Status.SERVIE:
            url = reverse("orders:invoice_scan", kwargs={"token": order.invoice_token})
            return redirect(f"{url}?release={release}")
        messages.info(
            request,
            _("Commande %(ref)s — table %(n)s (%(code)s) : %(status)s")
            % {
                "ref": order.order_ref,
                "n": order.table.number,
                "code": order.table.public_code,
                "status": order.get_status_display(),
            },
        )
        return redirect("orders:staff_detail", pk=order.pk)

    if table:
        payable = (
            table.orders.filter(status=Order.Status.SERVIE).order_by("-created_at").first()
        )
        if payable:
            url = reverse("orders:invoice_scan", kwargs={"token": payable.invoice_token})
            return redirect(f"{url}?release={release}")
        if table.status == Table.Status.OCCUPEE:
            messages.info(
                request,
                _(
                    "Table %(n)s (%(code)s) occupée, aucune facture à encaisser. "
                    "Libérez-la depuis la liste des tables si le service est terminé."
                )
                % {"n": table.number, "code": table.public_code},
            )
            return redirect("tables:serveur_home")
        messages.info(
            request,
            _("Table %(n)s (%(code)s) est libre.")
            % {"n": table.number, "code": table.public_code},
        )
        return redirect("tables:serveur_home")

    messages.error(request, _("Aucun code table ou facture correspondant."))
    return redirect("tables:serveur_home")
