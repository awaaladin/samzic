"""Site-wide template context."""

from django.conf import settings

from cart.cart import MAX_QUANTITY_PER_ITEM


def site(request):
    """Expose branding values so templates never hardcode the business name."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_PHONE": settings.SITE_PHONE,
        # base.html hands this to app.js so the "+" button knows the ceiling
        # without hardcoding it in two languages.
        "CART_MAX_QUANTITY": MAX_QUANTITY_PER_ITEM,
    }
