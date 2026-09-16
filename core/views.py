from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.permissions import admin_required, audit_required, staff_any
from cash.models import CashEntry
from menu.models import Category
from orders.models import Order
from reservations.models import Reservation
from tables.models import Table

from .forms import ContactForm, RestaurantForm
from .models import Restaurant


def home(request):
    """Public landing page with menu preview and live table board."""
    from django.db.models import Prefetch

    from menu.models import Dish
    from orders.cart import Cart

    categories = Category.objects.filter(is_active=True).prefetch_related(
        Prefetch("dishes", queryset=Dish.objects.filter(is_active=True))
    )[:3]
    tables = Table.objects.all()
    return render(
        request,
        "core/home.html",
        {
            "categories": categories,
            "cart": Cart(request),
            "tables": tables,
            "tables_free": tables.filter(status=Table.Status.LIBRE).count(),
            "tables_busy": tables.filter(status=Table.Status.OCCUPEE).count(),
        },
    )


def table_board_partial(request):
    """HTMX fragment: live table statuses for the homepage."""
    tables = Table.objects.all()
    return render(
        request,
        "core/partials/table_board.html",
        {
            "tables": tables,
            "tables_free": tables.filter(status=Table.Status.LIBRE).count(),
            "tables_busy": tables.filter(status=Table.Status.OCCUPEE).count(),
        },
    )


@staff_any
def dashboard(request):
    user = request.user
    # Role landings
    if user.is_serveur_role and not user.is_admin_role:
        return redirect("tables:serveur_home")
    if user.is_cuisine_role and not user.is_admin_role:
        return redirect("orders:staff_list")
    if user.is_caissier_role and not user.is_admin_role:
        return redirect("cash:ledger")

    today = timezone.localdate()
    orders_today = Order.objects.filter(created_at__date=today)
    paid_today = orders_today.filter(status=Order.Status.PAYEE)

    cash_in = CashEntry.objects.filter(type=CashEntry.Type.IN).aggregate(s=Sum("amount"))["s"] or 0
    cash_out = CashEntry.objects.filter(type=CashEntry.Type.OUT).aggregate(s=Sum("amount"))["s"] or 0

    pending_discounts = Order.objects.filter(discount_status="pending").count()

    context = {
        "orders_today_count": orders_today.count(),
        "orders_pending_count": Order.objects.filter(
            status__in=[
                Order.Status.EN_ATTENTE,
                Order.Status.ACCEPTEE,
                Order.Status.EN_PREPARATION,
                Order.Status.PRETE,
            ]
        ).count(),
        "revenue_today": paid_today.aggregate(s=Sum("total"))["s"] or 0,
        "tables_total": Table.objects.count(),
        "tables_occupied": Table.objects.filter(status=Table.Status.OCCUPEE).count(),
        "reservations_pending": Reservation.objects.filter(
            status=Reservation.Status.EN_ATTENTE
        ).count(),
        "reservations_today": Reservation.objects.filter(date=today).exclude(
            status__in=[Reservation.Status.REFUSEE, Reservation.Status.ANNULEE]
        ).count(),
        "cash_balance": cash_in - cash_out,
        "pending_discounts": pending_discounts,
        "latest_orders": Order.objects.select_related("table").order_by("-created_at")[:8],
        "tables": Table.objects.all(),
    }
    return render(request, "core/dashboard.html", context)


@admin_required
def restaurant_settings(request):
    from .forms import COLOR_PRESETS

    resto = Restaurant.get_solo()
    form = RestaurantForm(request.POST or None, request.FILES or None, instance=resto)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Paramètres du site enregistrés."))
        return redirect("core:settings")
    return render(
        request,
        "core/settings.html",
        {"form": form, "presets": COLOR_PRESETS, "restaurant_obj": resto},
    )


def contact(request):
    """Public contact page with info cards + message form."""
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return render(request, "core/contact_thanks.html")
    return render(request, "core/contact.html", {"form": form})


def legal_mentions(request):
    """Mentions légales."""
    return render(request, "core/legal.html")


def terms_of_use(request):
    """Politique d'utilisation / données."""
    return render(request, "core/terms.html")


def healthcheck(request):
    """Northflank / load-balancer health probe (no auth)."""
    from django.db import connection
    from django.http import JsonResponse

    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "error", "database": db_ok}, status=status)


@audit_required
def audit_log(request):
    """Staff action journal (admin / manager)."""
    from .models import AuditLog

    logs = AuditLog.objects.select_related("actor")[:200]
    return render(request, "core/audit_log.html", {"logs": logs})
