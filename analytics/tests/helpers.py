from datetime import datetime, time
from decimal import Decimal

from django.utils import timezone

from accounts.models import User
from cash.models import CashEntry
from menu.models import Category, Dish
from orders.models import Order, OrderItem
from reservations.models import Reservation
from tables.models import Table


def aware(dt: datetime) -> datetime:
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())


def make_user(username, role, password="pass1234"):
    user = User.objects.create_user(username=username, password=password, role=role)
    return user


def make_menu():
    starters, _ = Category.objects.get_or_create(name_fr="Entrées", defaults={"name_en": "Starters", "position": 0})
    mains, _ = Category.objects.get_or_create(name_fr="Plats", defaults={"name_en": "Mains", "position": 1})
    salad, _ = Dish.objects.get_or_create(
        category=starters,
        name_fr="Salade",
        defaults={"name_en": "Salad", "price": Decimal("5.00")},
    )
    pizza, _ = Dish.objects.get_or_create(
        category=mains,
        name_fr="Pizza",
        defaults={"name_en": "Pizza", "price": Decimal("10.00")},
    )
    return starters, mains, salad, pizza


def make_table(number=1):
    table, _ = Table.objects.get_or_create(number=number, defaults={"capacity": 4})
    return table


def make_order(
    *,
    table,
    dish,
    qty=1,
    status=Order.Status.PAYEE,
    when,
    paid_at=None,
    unit_price=None,
    discount_amount=Decimal("0"),
    discount_status="none",
    discount_requested_by=None,
):
    order = Order.objects.create(
        table=table,
        status=status,
        discount_amount=discount_amount,
        discount_status=discount_status,
        discount_requested_by=discount_requested_by,
    )
    OrderItem.objects.create(
        order=order,
        dish=dish,
        quantity=qty,
        unit_price=unit_price if unit_price is not None else dish.price,
    )
    order.refresh_total()
    paid = paid_at if paid_at is not None else (when if status == Order.Status.PAYEE else None)
    Order.objects.filter(pk=order.pk).update(created_at=when, paid_at=paid)
    order.refresh_from_db()
    return order


def make_reservation(*, name="Ada", on_date, at_time=None, status=Reservation.Status.CONFIRMEE, guests=2):
    return Reservation.objects.create(
        name=name,
        phone="000",
        date=on_date,
        time=at_time or time(19, 0),
        guests=guests,
        status=status,
    )


def make_cash(*, amount, entry_type=CashEntry.Type.IN, reason="test", order=None, when=None, user=None):
    entry = CashEntry.objects.create(
        type=entry_type,
        amount=amount,
        reason=reason,
        order=order,
        created_by=user,
    )
    if when:
        CashEntry.objects.filter(pk=entry.pk).update(created_at=when)
        entry.refresh_from_db()
    return entry
