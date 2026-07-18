from django import template

register = template.Library()


@register.filter
def cart_qty(cart, dish_id):
    """Return quantity of a dish in the session cart."""
    if not cart:
        return 0
    return cart.data.get("items", {}).get(str(dish_id), 0)
