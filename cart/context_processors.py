"""Makes the cart available to every template (navbar badge, mini summary)."""

from .models import get_cart


def cart(request):
    return {"cart": get_cart(request)}
