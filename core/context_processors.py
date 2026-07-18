from django.conf import settings


def restaurant(request):
    """Expose the restaurant profile and currency to every template."""
    from .models import Restaurant

    try:
        resto = Restaurant.get_solo()
    except Exception:  # during initial migrations the table may not exist yet
        resto = None
    return {"restaurant": resto, "CURRENCY": settings.CURRENCY}
