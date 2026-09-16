from decimal import Decimal, InvalidOperation as DecimalError

from django.contrib import messages
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.permissions import menu_required
from orders.cart import Cart

from .forms import CategoryForm, DishForm
from .models import Category, Dish


def public_menu(request):
    """Public menu: search + filters, then add to cart and Commander → scan QR."""
    q = (request.GET.get("q") or "").strip()
    cat_raw = request.GET.get("cat") or ""
    max_raw = (request.GET.get("max") or "").strip().replace(",", ".")
    sort = request.GET.get("sort") or ""

    max_price = None
    if max_raw:
        try:
            max_price = Decimal(max_raw)
        except (DecimalError, ValueError):
            max_price = None
        if max_price is not None and max_price < 0:
            max_price = None

    dishes = Dish.objects.filter(is_active=True)
    if q:
        dishes = dishes.filter(
            Q(name_fr__icontains=q)
            | Q(name_en__icontains=q)
            | Q(description_fr__icontains=q)
            | Q(description_en__icontains=q)
        )
    if max_price is not None:
        dishes = dishes.filter(price__lte=max_price)
    if sort == "price_asc":
        dishes = dishes.order_by("price", "name_fr")
    elif sort == "price_desc":
        dishes = dishes.order_by("-price", "name_fr")
    else:
        dishes = dishes.order_by("name_fr")

    categories = Category.objects.filter(is_active=True)
    if cat_raw.isdigit():
        categories = categories.filter(pk=int(cat_raw))
    categories = categories.prefetch_related(Prefetch("dishes", queryset=dishes))

    cart = Cart(request)
    filters = {
        "q": q,
        "cat": cat_raw if cat_raw.isdigit() else "",
        "max": max_raw,
        "sort": sort,
    }
    return render(
        request,
        "menu/public_menu.html",
        {
            "categories": categories,
            "all_categories": Category.objects.filter(is_active=True),
            "cart": cart,
            "filters": filters,
            "result_count": dishes.count(),
            "has_filters": bool(q or filters["cat"] or filters["max"] or sort),
        },
    )


def dish_detail(request, pk):
    """Dish detail panel for the menu drawer/modal (HTMX or full)."""
    dish = get_object_or_404(Dish, pk=pk, is_active=True)
    cart = Cart(request)
    return render(
        request,
        "menu/partials/dish_detail.html",
        {"dish": dish, "cart": cart},
    )


# ----- Staff CRUD -----


@menu_required
def staff_menu(request):
    categories = Category.objects.prefetch_related("dishes")
    return render(request, "menu/staff_menu.html", {"categories": categories})


@menu_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Catégorie créée."))
        return redirect("menu:staff")
    return render(
        request, "menu/category_form.html", {"form": form, "title": _("Nouvelle catégorie")}
    )


@menu_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Catégorie mise à jour."))
        return redirect("menu:staff")
    return render(
        request,
        "menu/category_form.html",
        {"form": form, "title": _("Modifier « %(name)s »") % {"name": category.name_fr}},
    )


@menu_required
def category_delete(request, pk):
    from django.db.models.deletion import ProtectedError

    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        name = category.name_fr
        try:
            category.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "Impossible de supprimer « %(name)s » : des plats liés à des commandes "
                    "empêchent la suppression. Désactivez la catégorie ou ses plats."
                )
                % {"name": name},
            )
            return redirect("menu:staff")
        messages.success(request, _("Catégorie « %(name)s » supprimée.") % {"name": name})
        return redirect("menu:staff")
    return render(request, "menu/category_confirm_delete.html", {"category": category})


@menu_required
def dish_create(request):
    form = DishForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Plat créé."))
        return redirect("menu:staff")
    return render(request, "menu/dish_form.html", {"form": form, "title": _("Nouveau plat")})


@menu_required
def dish_update(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    form = DishForm(request.POST or None, request.FILES or None, instance=dish)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Plat mis à jour."))
        return redirect("menu:staff")
    return render(
        request,
        "menu/dish_form.html",
        {"form": form, "title": _("Modifier « %(name)s »") % {"name": dish.name_fr}},
    )


@menu_required
def dish_toggle(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == "POST":
        dish.is_active = not dish.is_active
        dish.save(update_fields=["is_active"])
    return redirect("menu:staff")


@menu_required
def dish_delete(request, pk):
    from django.db.models.deletion import ProtectedError

    dish = get_object_or_404(Dish, pk=pk)
    linked = dish.order_items.exists()
    if request.method == "POST":
        name = dish.name_fr
        try:
            dish.delete()
        except ProtectedError:
            messages.error(
                request,
                _(
                    "Impossible de supprimer « %(name)s » : des commandes y sont liées. "
                    "Désactivez-le plutôt pour le retirer du menu."
                )
                % {"name": name},
            )
            return redirect("menu:staff")
        messages.success(request, _("Plat « %(name)s » supprimé.") % {"name": name})
        return redirect("menu:staff")
    return render(
        request,
        "menu/dish_confirm_delete.html",
        {"dish": dish, "linked": linked},
    )
