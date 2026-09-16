def cart(request):
    """Expose the session cart to every public template."""
    from .cart import Cart

    try:
        return {"cart": Cart(request)}
    except Exception:  # migrations / no session
        return {"cart": None}


def staff_chrome(request):
    """Waiters stay in the floor UI instead of the admin rail."""
    user = getattr(request, "user", None)
    floor = bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_serveur_role", False)
        and not getattr(user, "is_admin_role", False)
    )
    return {
        "is_floor_serveur": floor,
        "staff_chrome": "serveur_base.html" if floor else "staff_base.html",
    }
