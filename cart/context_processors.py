"""Makes the cart available to every template (navbar badge, mini summary)."""

from .cart import Cart


def cart(request):
    return {"cart": Cart(request)}
