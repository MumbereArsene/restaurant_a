"""Session cart for the public menu (no table required until checkout).

Structure stored in session under ``cart``:
    {"items": {"<dish_id>": qty}}
"""

from decimal import Decimal

from menu.models import Dish

SESSION_KEY = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        data = self.session.get(SESSION_KEY)
        if not data or "items" not in data:
            data = {"items": {}}
            self.session[SESSION_KEY] = data
        # Drop legacy token-bound carts cleanly
        if "token" in data:
            data.pop("token", None)
            self.session[SESSION_KEY] = data
        self.data = data

    def _save(self):
        self.session[SESSION_KEY] = self.data
        self.session.modified = True

    def add(self, dish_id: int, qty: int = 1):
        items = self.data["items"]
        items[str(dish_id)] = items.get(str(dish_id), 0) + qty
        self._save()

    def set_qty(self, dish_id: int, qty: int):
        items = self.data["items"]
        if qty <= 0:
            items.pop(str(dish_id), None)
        else:
            items[str(dish_id)] = qty
        self._save()

    def remove(self, dish_id: int):
        self.data["items"].pop(str(dish_id), None)
        self._save()

    def clear(self):
        self.data["items"] = {}
        self._save()

    @property
    def count(self) -> int:
        return sum(self.data["items"].values())

    def qty_for(self, dish_id: int) -> int:
        return self.data["items"].get(str(dish_id), 0)

    def entries(self):
        """Yield (dish, qty, subtotal) for available dishes in the cart."""
        ids = [int(i) for i in self.data["items"]]
        dishes = {
            d.pk: d
            for d in Dish.objects.filter(pk__in=ids, is_active=True).select_related("category")
        }
        for raw_id, qty in self.data["items"].items():
            dish = dishes.get(int(raw_id))
            if dish:
                yield dish, qty, dish.price * qty

    @property
    def total(self) -> Decimal:
        return sum((sub for _, _, sub in self.entries()), Decimal("0"))
