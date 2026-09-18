import io

import qrcode
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.permissions import encaisser_required, staff_any
from menu.models import Dish
from tables.models import Table

from .cart import Cart
from .models import Order, OrderItem


def _wants_json(request) -> bool:
    return (
        request.headers.get("HX-Request")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _resolve_checkout_contact(request):
    """Return (customer, email, phone, error) from checkout POST / session user."""
    email = (request.POST.get("guest_email") or "").strip().lower()
    phone = (request.POST.get("guest_phone") or "").strip()
    create_account = request.POST.get("create_account") == "1"
    password = request.POST.get("password") or ""
    user = request.user if request.user.is_authenticated else None

    if user and getattr(user, "is_client_role", False):
        return user, email or (user.email or ""), phone or (user.phone or ""), None

    if create_account:
        if not email:
            return None, email, phone, _("Un email est requis pour créer un compte.")
        if len(password) < 8:
            return None, email, phone, _("Le mot de passe doit contenir au moins 8 caractères.")
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(
            email__iexact=email
        ).exists():
            return None, email, phone, _("Un compte existe déjà avec cet email. Connectez-vous.")
        customer = User(username=email, email=email, phone=phone, role=User.Role.CLIENT)
        customer.set_password(password)
        customer.save()
        login(request, customer)
        return customer, email, phone, None

    if not email and not phone:
        return None, email, phone, _(
            "Indiquez un WhatsApp, un email, ou créez un compte pour recevoir la facture."
        )
    return None, email, phone, None


def _place_order(
    request,
    table: Table,
    note: str = "",
    *,
    customer=None,
    guest_email: str = "",
    guest_phone: str = "",
) -> Order | None:
    """Create an order from the session cart for the given table."""
    cart = Cart(request)
    entries = list(cart.entries())
    if not entries:
        return None

    with transaction.atomic():
        order = Order.objects.create(
            table=table,
            note=note.strip(),
            customer=customer,
            guest_email=guest_email,
            guest_phone=guest_phone,
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(order=order, dish=dish, quantity=qty, unit_price=dish.price)
                for dish, qty, _sub in entries
            ]
        )
        order.refresh_total()
        if table.status != Table.Status.OCCUPEE:
            table.occupy()

    cart.clear()
    request.session["checkout_table_token"] = table.public_code
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
    """Collect invoice contact + table public code."""
    cart = Cart(request)
    if not cart.count:
        messages.error(request, _("Votre panier est vide."))
        return redirect("menu:public")
    from tables.codes import resolve_table

    preset = request.session.get("checkout_table_token")
    table = resolve_table(preset) if preset else None
    return render(request, "orders/scan.html", {"cart": cart, "preset_table": table})


@require_POST
def checkout_submit(request):
    """Place the order after a valid table public code is entered."""
    from tables.codes import resolve_table

    customer, email, phone, error = _resolve_checkout_contact(request)
    if error:
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("orders:checkout_scan")

    token = (request.POST.get("token") or request.session.get("checkout_table_token") or "").strip()
    table = resolve_table(token)
    if not table:
        msg = _("Code table invalide. Saisissez le code affiché sur votre table.")
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("orders:checkout_scan")

    request.session["checkout_table_token"] = table.public_code
    order = _place_order(
        request,
        table,
        note=request.POST.get("note", ""),
        customer=customer,
        guest_email=email,
        guest_phone=phone,
    )
    if not order:
        messages.error(request, _("Votre panier est vide."))
        return redirect("menu:public")

    if _wants_json(request):
        return JsonResponse(
            {
                "ok": True,
                "redirect": f"/order/{table.public_code}/confirmation/{order.invoice_token}/",
            }
        )
    return redirect(
        "orders:confirmation", token=table.public_code, invoice_token=order.invoice_token
    )


def order_confirmation(request, token, invoice_token):
    from tables.codes import resolve_table

    table = resolve_table(token)
    if not table:
        table = get_object_or_404(Table, qr_token=token)
    order = get_object_or_404(
        Order.objects.select_related("customer", "table"),
        invoice_token=invoice_token,
        table=table,
    )
    return render(request, "orders/confirmation.html", {"table": table, "order": order})


def order_qr_landing(request, token):
    """Remember the table from its public code (or legacy internal token)."""
    from tables.codes import resolve_table

    table = resolve_table(token)
    if not table:
        table = get_object_or_404(Table, qr_token=token)
    cart = Cart(request)
    request.session["checkout_table_token"] = table.public_code
    if cart.count:
        messages.info(
            request,
            _("Bienvenue à la table %(code)s (table %(n)s).")
            % {"code": table.public_code, "n": table.number},
        )
        return redirect("orders:checkout_scan")
    messages.info(
        request,
        _("Table %(n)s — code %(code)s. Choisissez vos plats, puis Commander.")
        % {"n": table.number, "code": table.public_code},
    )
    return redirect("menu:public")


def public_invoice(request, token):
    """Client-facing invoice (email / WhatsApp / compte)."""
    order = get_object_or_404(
        Order.objects.select_related("table", "customer").prefetch_related("items__dish"),
        invoice_token=token,
    )
    if not order.has_invoice:
        return render(
            request,
            "orders/public_invoice.html",
            {"order": order, "pending": True},
        )
    return render(request, "orders/public_invoice.html", {"order": order, "pending": False})


@login_required(login_url="accounts:client_login")
def client_invoices(request):
    if not request.user.is_client_role:
        messages.error(request, _("Espace réservé aux clients."))
        return redirect("accounts:login")
    orders = (
        Order.objects.filter(customer=request.user)
        .select_related("table")
        .prefetch_related("items__dish")
    )
    return render(request, "orders/client_invoices.html", {"orders": orders})


# ----- Staff -----

OPEN_STATUSES = list(Order.OPEN_STATUSES)

STAFF_FILTER_STATUSES = [
    (Order.Status.EN_ATTENTE, _("En attente")),
    (Order.Status.ACCEPTEE, _("Acceptée")),
    (Order.Status.SERVIE, _("Servie")),
    (Order.Status.PAYEE, _("Payée")),
    (Order.Status.ANNULEE, _("Annulée")),
]


def _order_qs():
    return Order.objects.select_related("table", "customer").prefetch_related("items__dish")


def _is_floor_serveur(user) -> bool:
    return bool(
        getattr(user, "is_serveur_role", False) and not getattr(user, "is_admin_role", False)
    )


def _after_staff_order(request):
    nxt = request.POST.get("next") or ""
    if nxt.startswith("/"):
        return redirect(nxt)
    if _is_floor_serveur(request.user):
        return redirect("tables:serveur_home")
    return redirect("orders:staff_list")


def _redirect_payment_block(request, order):
    """Return a redirect if this order cannot be cashed, else None."""
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
    if order.status != Order.Status.SERVIE:
        messages.error(
            request,
            _("La commande doit être servie avant d'encaisser (facture réglée)."),
        )
        return redirect("orders:staff_detail", pk=order.pk)
    return None


@staff_any
def staff_orders(request):
    if _is_floor_serveur(request.user) and not request.headers.get("HX-Request"):
        return redirect("tables:serveur_home")
    status = request.GET.get("status", "")
    orders = _order_qs()
    if status == Order.Status.ACCEPTEE:
        orders = orders.filter(status__in=Order.ACCEPTED_LIKE)
    elif status:
        orders = orders.filter(status=status)
    context = {
        "orders": orders[:100],
        "current_status": status,
        "statuses": STAFF_FILTER_STATUSES,
    }
    if request.headers.get("HX-Request"):
        return render(request, "orders/_order_list.html", context)
    return render(request, "orders/staff_orders.html", context)


@staff_any
def staff_order_detail(request, pk):
    order = get_object_or_404(_order_qs(), pk=pk)
    return render(
        request,
        "orders/staff_order_detail.html",
        {
            "order": order,
            "can_pay": order.is_payable,
            "next_status": order.next_status,
            "can_edit_items": order.status not in (Order.Status.PAYEE, Order.Status.ANNULEE),
            "add_dishes": Dish.objects.filter(is_active=True).select_related("category"),
        },
    )


@staff_any
@require_POST
def staff_order_edit_item(request, pk):
    """Waiter adjusts a line of an open order (add / inc / dec / remove)."""
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    if order.status in (Order.Status.PAYEE, Order.Status.ANNULEE):
        messages.error(request, _("Impossible de modifier une commande payée ou annulée."))
        return _after_staff_order(request)

    action = request.POST.get("action", "inc")
    dish_pk = request.POST.get("dish_id") or ""
    dish = Dish.objects.filter(pk=dish_pk, is_active=True).first() if dish_pk.isdigit() else None
    if not dish:
        messages.error(request, _("Plat introuvable."))
        return redirect("orders:staff_detail", pk=order.pk)

    item = order.items.filter(dish=dish).first()
    current = item.quantity if item else 0
    if action == "inc":
        qty = current + 1
    elif action == "dec":
        qty = current - 1
    elif action == "remove":
        qty = 0
    elif action == "set":
        raw = request.POST.get("quantity") or ""
        try:
            qty = int(raw)
        except (TypeError, ValueError):
            qty = 0
    else:
        qty = current

    if qty > 0:
        if item:
            item.quantity = qty
            item.save(update_fields=["quantity"])
        else:
            OrderItem.objects.create(
                order=order,
                dish=dish,
                quantity=qty,
                unit_price=dish.price,
                note=request.POST.get("note", "")[:255],
            )
    elif item:
        item.delete()

    order.refresh_total()
    log_action(
        request.user,
        "order.items",
        _("Commande #%(id)s modifiée — %(qty)s × « %(name)s »")
        % {"id": order.pk, "qty": qty, "name": dish.name_fr},
        object_type="Order",
        object_id=order.pk,
    )
    messages.success(
        request,
        _("%(qty)s × « %(name)s » sur la commande #%(id)s (nouveau total %(total)s).")
        % {"qty": qty, "name": dish.name_fr, "id": order.pk, "total": order.total},
    )
    return _after_staff_order(request)


@staff_any
def staff_order_ticket(request, pk):
    """Printable kitchen ticket."""
    order = get_object_or_404(_order_qs(), pk=pk)
    return render(request, "orders/kitchen_ticket.html", {"order": order})


@staff_any
def staff_order_invoice(request, pk):
    """Printable invoice with table/invoice codes (after the order has been served)."""
    order = get_object_or_404(_order_qs(), pk=pk)
    if not order.has_invoice:
        messages.error(request, _("Servez la commande pour générer la facture."))
        return redirect("orders:staff_detail", pk=order.pk)
    return render(
        request,
        "orders/invoice.html",
        {"order": order, "whatsapp_url": order.whatsapp_url(request)},
    )


def staff_invoice_qr_png(request, token):
    """QR on the invoice: public facture URL (waiter scans it in Espace serveur)."""
    order = get_object_or_404(Order, invoice_token=token)
    img = qrcode.make(order.public_invoice_url(request), box_size=10, border=2)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@encaisser_required
def staff_invoice_scan(request, token):
    """Waiter entered invoice/table code → same payment screen as Facture réglée."""
    from tables.codes import resolve_order_by_code

    order = resolve_order_by_code(token)
    if not order:
        order = get_object_or_404(_order_qs(), invoice_token=token)
    blocked = _redirect_payment_block(request, order)
    if blocked:
        return blocked
    release = request.GET.get("release", "1")
    if release not in ("0", "1"):
        release = "1"
    return render(
        request,
        "orders/pay_confirm.html",
        {
            "order": order,
            "from_scan": True,
            "checked_release": release,
            "payment_methods": Order.PaymentMethod.choices,
        },
    )

@staff_any
@require_POST
def staff_order_advance(request, pk):
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    next_status = order.next_status
    if next_status and order.advance():
        order.refresh_from_db()
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
        if order.status == Order.Status.SERVIE:
            notice = order.notify_invoice(request)
            if notice["email"]:
                messages.info(request, _("Facture envoyée par email."))
            return redirect("orders:staff_invoice", pk=order.pk)
    return _after_staff_order(request)


@encaisser_required
def staff_order_pay_confirm(request, pk):
    """Manual pay screen — waiters must scan the invoice instead."""
    order = get_object_or_404(_order_qs(), pk=pk)
    if _is_floor_serveur(request.user):
        messages.info(
            request,
            _("Saisissez le code facture ou le code table (onglet Rechercher)."),
        )
        return redirect("tables:serveur_home")
    blocked = _redirect_payment_block(request, order)
    if blocked:
        return blocked
    return render(
        request,
        "orders/pay_confirm.html",
        {
            "order": order,
            "checked_release": "1",
            "payment_methods": Order.PaymentMethod.choices,
        },
    )


@encaisser_required
@require_POST
def staff_order_mark_paid(request, pk):
    from core.audit import log_action

    order = get_object_or_404(Order, pk=pk)
    if _is_floor_serveur(request.user) and request.POST.get("from_scan") != "1":
        messages.error(
            request,
            _("Le serveur doit saisir le code facture ou le code table pour encaisser."),
        )
        return redirect("tables:serveur_home")
    blocked = _redirect_payment_block(request, order)
    if blocked:
        return blocked

    method = (request.POST.get("payment_method") or "").strip()
    newly_paid = order.mark_paid(request.user, payment_method=method)
    order.refresh_from_db()
    release_table = request.POST.get("release_table") == "1"
    if release_table:
        order.table.release_if_idle()
        order.table.refresh_from_db()
    if newly_paid:
        log_action(
            request.user,
            "order.paid",
            _("Commande #%(id)s encaissée — %(total)s (table %(n)s, %(method)s)")
            % {
                "id": order.pk,
                "total": order.total,
                "n": order.table.number,
                "method": order.get_payment_method_display(),
            },
            object_type="Order",
            object_id=order.pk,
        )
        if release_table:
            messages.success(
                request,
                _("Commande #%(id)s encaissée — %(total)s (%(method)s). Table libérée.")
                % {
                    "id": order.pk,
                    "total": order.total,
                    "method": order.get_payment_method_display(),
                },
            )
        else:
            messages.success(
                request,
                _("Commande #%(id)s encaissée — %(total)s (%(method)s). Table toujours occupée.")
                % {
                    "id": order.pk,
                    "total": order.total,
                    "method": order.get_payment_method_display(),
                },
            )
    else:
        messages.info(request, _("Cette commande est déjà payée."))
    return _after_staff_order(request)


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
        order.table.release_if_idle()
        log_action(
            request.user,
            "order.cancel",
            _("Commande #%(id)s annulée") % {"id": order.pk},
            object_type="Order",
            object_id=order.pk,
        )
        messages.success(request, _("Commande #%(id)s annulée.") % {"id": order.pk})
    return _after_staff_order(request)
