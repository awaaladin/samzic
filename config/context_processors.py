"""Site-wide template context."""

import hashlib
from functools import lru_cache

from django.conf import settings

from cart.cart import MAX_QUANTITY_PER_ITEM

# Files whose contents decide the cache-busting version.
_VERSIONED_ASSETS = ("css/tailwind.css", "css/app.css", "js/app.js")


@lru_cache(maxsize=1)
def _asset_version():
    """Short hash of the site's own CSS/JS, computed once per process.

    Appended as ?v=... so a browser (or CDN) that cached an older stylesheet or
    script fetches the new one the moment a deploy changes it, instead of
    running old JavaScript against new markup until its cache expires.
    """
    digest = hashlib.md5(usedforsecurity=False)
    for name in _VERSIONED_ASSETS:
        path = settings.BASE_DIR / "static" / name
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(name.encode())
    return digest.hexdigest()[:10]


def site(request):
    """Expose branding values so templates never hardcode the business name."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_PHONE": settings.SITE_PHONE,
        # base.html hands this to app.js so the "+" button knows the ceiling
        # without hardcoding it in two languages.
        "CART_MAX_QUANTITY": MAX_QUANTITY_PER_ITEM,
        "ASSET_VERSION": _asset_version(),
    }
