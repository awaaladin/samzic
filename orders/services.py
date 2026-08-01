"""Order money maths.

Delivery pricing lives here (not in a view or template) so there is exactly one
place to change it, and so the cart page and the checkout page can never quote
different numbers.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

TWO_PLACES = Decimal("0.01")


def _money(value):
    """Coerce settings strings / floats to a rounded 2dp Decimal."""
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def get_delivery_fee(subtotal):
    """Free above the threshold, flat fee otherwise. Empty cart pays nothing."""
    subtotal = _money(subtotal)
    if subtotal <= 0:
        return _money(0)
    if subtotal >= _money(settings.FREE_DELIVERY_THRESHOLD):
        return _money(0)
    return _money(settings.DELIVERY_FEE)


def get_order_totals(subtotal):
    """Everything the cart/checkout templates need to show a price breakdown."""
    subtotal = _money(subtotal)
    delivery_fee = get_delivery_fee(subtotal)
    threshold = _money(settings.FREE_DELIVERY_THRESHOLD)

    return {
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": _money(subtotal + delivery_fee),
        "free_delivery_threshold": threshold,
        # Drives the "spend ₦X more for free delivery" nudge.
        "amount_to_free_delivery": (
            _money(threshold - subtotal) if 0 < subtotal < threshold else _money(0)
        ),
        "qualifies_for_free_delivery": subtotal >= threshold,
    }
