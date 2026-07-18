from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.permissions import encaisser_required, staff_any
from menu.models import Category, Dish
from tables.models import Table

from .cart import Cart
from .models import Order, OrderItem


def _place_order(request, table: Table, note: str = "") -> Order | None:
    """Create an order from the session cart for the given table."""
    cart = Cart(request)
    entries = list(cart.entries())
    if not entries:
        return None

    with transaction.atomic():
        order = Order.objects.create(table=table, note=note.strip())
        OrderItem.objects.bulk_create(
            [
                OrderItem(order=order, dish=dish, quantity=qty, unit_price=dish.price)
                for dish, qty, _sub in entries
            ]
        )
        order.refresh_total()
        if table.status != Table.Status.OCCUPEE:
            table.status = Table.Status.OCCUPEE
            table.save(update_fields=["status"])

    cart.clear()
    return order


# ----- Public cart (menu-first flow) -----


def _htmx_cart_response(request, dish=None):
    """Return cart bar (+ optional dish qty control) for HTMX without full reload."""
    cart = Cart(request)
    context = {"cart": cart, "dish": dish}
    return render(request, "orders/partials/cart_htmx.html", context)


@require_POST
def cart_add(request):
    dish = get_object_or_404(Dish, pk=request.POST.get("dish_id"), is_active=True)
    Cart(request).add(dish.pk)
    if request.headers.get("HX-Request"):
        return _htmx_cart_response(request, dish=dish)
    messages.success(request, _("« %(name)s » ajouté.") % {"name": dish.name})
    next_url = request.POST.get("next") or "menu:public"
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(next_url)


@require_POST
def cart_update(request):
    cart = Cart(request)
    dish_id = int(request.POST.get("dish_id"))
    action = request.POST.get("action")
    current = cart.data["items"].get(str(dish_id), 0)
    if action == "inc":
        cart.set_qty(dish_id, current + 1)
    elif action == "dec":
        cart.set_qty(dish_id, current - 1)
    elif action == "remove":
        cart.remove(dish_id)
    dish = Dish.objects.filter(pk=dish_id).first()
    if request.headers.get("HX-Request"):
        return _htmx_cart_response(request, dish=dish)
    next_url = request.POST.get("next") or "/menu/panier/"
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("orders:cart")


def cart_view(request):
    cart = Cart(request)
    return render(request, "orders/cart.html", {"cart": cart})


def checkout_scan(request):
    """Open the camera scanner after the customer builds their cart."""
    cart = Cart(request)
    if not cart.count:
        messages.error(request, _("Votre panier est vide."))
        return redirect("menu:public")
    return render(request, "orders/scan.html", {"cart": cart})


@require_POST
def checkout_submit(request):
    """Place the order after a valid table QR token is scanned."""
    token = (request.POST.get("token") or "").strip()
    # Accept full order URLs pasted/scanned as well as raw tokens
    if "/order/" in token:
        token = token.rstrip("/").split("/order/")[-1].split("/")[0].split("?")[0]

    table = Table.objects.filter(qr_token=token).first()
    if not table:
        if request.headers.get("HX-Request") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("QR code invalide. Scannez le QR de votre table.")}, status=400)
        messages.error(request, _("QR code invalide. Scannez le QR de votre table."))
        return redirect("orders:checkout_scan")

    order = _place_order(request, table, note=request.POST.get("note", ""))
    if not order:
        messages.error(request, _("Votre panier est vide."))
        return redirect("menu:public")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "redirect": f"/order/{table.qr_token}/confirmation/{order.pk}/",
            }
        )
    return redirect("orders:confirmation", token=table.qr_token, pk=order.pk)


def order_confirmation(request, token, pk):
    table = get_object_or_404(Table, qr_token=token)
    order = get_object_or_404(Order, pk=pk, table=table)
    return render(request, "orders/confirmation.html", {"table": table, "order": order})


def order_qr_landing(request, token):
    """Physical QR:
    - Serveur/admin connecté → page pour libérer la table
    - Client avec panier → commande auto
    - Sinon → menu
    """
    table = get_object_or_404(Table, qr_token=token)
    user = request.user
    if user.is_authenticated and (
        getattr(user, "is_admin_role", False)
        or getattr(user, "is_serveur_role", False)
        or getattr(user, "is_manager_role", False)
        or getattr(user, "can_free_tables", False)
    ):
        return redirect("tables:free_confirm", token=table.qr_token)

    cart = Cart(request)
    if cart.count:
        order = _place_order(request, table)
        if order:
            messages.success(
                request,
                _("Commande #%(id)s envoyée pour la table %(n)s.")
                % {"id": order.pk, "n": table.number},
            )
            return redirect("orders:confirmation", token=table.qr_token, pk=order.pk)
    messages.info(
        request,
        _("Table %(n)s — choisissez vos plats, puis cliquez sur Commander.")
        % {"n": table.number},
    )
    return redirect("menu:public")


# ----- Staff -----

WORKFLOW = {
    Order.Status.EN_ATTENTE: Order.Status.EN_PREPARATION,
    Order.Status.EN_PREPARATION: Order.Status.PRETE,
    Order.Status.PRETE: Order.Status.SERVIE,
}

OPEN_STATUSES = [
    Order.Status.EN_ATTENTE,
    Order.Status.EN_PREPARATION,
    Order.Status.PRETE,
    Order.Status.SERVIE,
]

PAYABLE_STATUSES = [
    Order.Status.PRETE,
    Order.Status.SERVIE,
]


@staff_any
def staff_orders(request):
    status = request.GET.get("status", "")
    orders = Order.objects.select_related("table").prefetch_related("items__dish")
    if status:
        orders = orders.filter(status=status)
    context = {
        "orders": orders[:100],
        "current_status": status,
        "statuses": Order.Status.choices,
    }
    if request.headers.get("HX-Request"):
        return render(request, "orders/_order_list.html", context)
    return render(request, "orders/staff_orders.html", context)


@staff_any
def staff_order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related("items__dish"), pk=pk
    )
    return render(
        request,
        "orders/staff_order_detail.html",
        {
            "order": order,
            "can_pay": order.status in PAYABLE_STATUSES,
            "next_status": WORKFLOW.get(order.status),
        },
    )


@staff_any
def staff_order_ticket(request, pk):
    """Printable kitchen ticket."""
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related("items__dish"), pk=pk
    )
    return render(request, "orders/kitchen_ticket.html", {"order": order})


@staff_any
@require_POST
def staff_order_advance(request, pk):
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    next_status = WORKFLOW.get(order.status)
    if next_status:
        order.status = next_status
        order.save(update_fields=["status"])
        log_action(
            request.user,
            "order.advance",
            _("Commande #%(id)s → %(status)s")
            % {"id": order.pk, "status": order.get_status_display()},
            object_type="Order",
            object_id=order.pk,
        )
        messages.success(
            request,
            _("Commande #%(id)s → %(status)s")
            % {"id": order.pk, "status": order.get_status_display()},
        )
    return redirect(request.POST.get("next") or "orders:staff_list")


@encaisser_required
def staff_order_pay_confirm(request, pk):
    """Clear payment confirmation screen for serveur/caissier/manager/admin."""
    order = get_object_or_404(
        Order.objects.select_related("table").prefetch_related("items__dish"), pk=pk
    )
    if order.status == Order.Status.ANNULEE:
        messages.error(request, _("Impossible d'encaisser une commande annulée."))
        return redirect("orders:staff_detail", pk=order.pk)
    if order.status == Order.Status.PAYEE:
        messages.info(request, _("Cette commande est déjà payée."))
        return redirect("orders:staff_detail", pk=order.pk)
    if order.discount_status == "pending":
        messages.error(
            request,
            _("Une remise est en attente de validation manager avant encaissement."),
        )
        return redirect("orders:staff_detail", pk=order.pk)
    return render(request, "orders/pay_confirm.html", {"order": order})


@encaisser_required
@require_POST
def staff_order_mark_paid(request, pk):
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    if order.status == Order.Status.ANNULEE:
        messages.error(request, _("Impossible d'encaisser une commande annulée."))
        return redirect("orders:staff_detail", pk=order.pk)
    if order.status == Order.Status.PAYEE:
        messages.info(request, _("Cette commande est déjà payée."))
        return redirect("orders:staff_detail", pk=order.pk)
    if order.discount_status == "pending":
        messages.error(
            request,
            _("Remise en attente — validation manager requise avant paiement."),
        )
        return redirect("orders:staff_detail", pk=order.pk)

    order.mark_paid(request.user)
    if not order.table.orders.filter(status__in=OPEN_STATUSES).exists():
        order.table.status = Table.Status.LIBRE
        order.table.save(update_fields=["status"])
    log_action(
        request.user,
        "order.paid",
        _("Commande #%(id)s encaissée — %(total)s (table %(n)s)")
        % {"id": order.pk, "total": order.total, "n": order.table.number},
        object_type="Order",
        object_id=order.pk,
    )
    messages.success(
        request,
        _("Commande #%(id)s encaissée — %(total)s.")
        % {"id": order.pk, "total": order.total},
    )
    return redirect(request.POST.get("next") or "orders:staff_list")


@staff_any
@require_POST
def staff_order_discount(request, pk):
    """Request or apply a discount on an unpaid order."""
    from decimal import Decimal, InvalidOperation

    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    if order.status in (Order.Status.PAYEE, Order.Status.ANNULEE):
        messages.error(request, _("Impossible de modifier la remise sur cette commande."))
        return redirect("orders:staff_detail", pk=order.pk)
    if not request.user.can_encaisser and not request.user.can_approve_discount:
        messages.error(request, _("Vous ne pouvez pas demander de remise."))
        return redirect("orders:staff_detail", pk=order.pk)

    try:
        amount = Decimal(request.POST.get("discount_amount") or "0")
    except (InvalidOperation, TypeError):
        messages.error(request, _("Montant de remise invalide."))
        return redirect("orders:staff_detail", pk=order.pk)

    reason = request.POST.get("discount_reason", "")
    auto = request.user.can_approve_discount
    order.apply_discount(amount, reason, request.user, auto_approve=auto)
    log_action(
        request.user,
        "order.discount",
        _("Remise %(amt)s sur commande #%(id)s (%(status)s)")
        % {"amt": order.discount_amount, "id": order.pk, "status": order.discount_status},
        object_type="Order",
        object_id=order.pk,
    )
    if order.discount_status == "pending":
        messages.info(request, _("Remise demandée — en attente de validation manager."))
    elif order.discount_status == "approved":
        messages.success(request, _("Remise appliquée."))
    else:
        messages.success(request, _("Remise retirée."))
    return redirect("orders:staff_detail", pk=order.pk)


@staff_any
@require_POST
def staff_order_discount_decide(request, pk):
    """Manager/admin approves or rejects a pending discount."""
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    if not request.user.can_approve_discount:
        messages.error(request, _("Seuls le manager ou l'admin peuvent valider une remise."))
        return redirect("orders:staff_detail", pk=order.pk)

    decision = request.POST.get("decision")
    if decision == "approve" and order.approve_discount(request.user):
        log_action(
            request.user,
            "order.discount_approve",
            _("Remise approuvée sur commande #%(id)s") % {"id": order.pk},
            object_type="Order",
            object_id=order.pk,
        )
        messages.success(request, _("Remise approuvée."))
    elif decision == "reject" and order.reject_discount(request.user):
        log_action(
            request.user,
            "order.discount_reject",
            _("Remise refusée sur commande #%(id)s") % {"id": order.pk},
            object_type="Order",
            object_id=order.pk,
        )
        messages.success(request, _("Remise refusée."))
    else:
        messages.error(request, _("Aucune remise en attente."))
    return redirect("orders:staff_detail", pk=order.pk)


@staff_any
@require_POST
def staff_order_cancel(request, pk):
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    if order.status == Order.Status.PAYEE:
        messages.error(request, _("Impossible d'annuler une commande déjà payée."))
    else:
        order.status = Order.Status.ANNULEE
        order.save(update_fields=["status"])
        log_action(
            request.user,
            "order.cancel",
            _("Commande #%(id)s annulée") % {"id": order.pk},
            object_type="Order",
            object_id=order.pk,
        )
        messages.success(request, _("Commande #%(id)s annulée.") % {"id": order.pk})
    return redirect(request.POST.get("next") or "orders:staff_list")
