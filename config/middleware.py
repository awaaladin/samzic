"""Project middleware."""

from django.core.exceptions import MiddlewareNotUsed
from django.shortcuts import render
from django.conf import settings


class BrandedErrorPagesMiddleware:
    """Serve the site's own error pages even while DEBUG is on.

    Django only routes to handler400/403/404 when DEBUG=False; with DEBUG on it
    substitutes its own yellow debug page. That is the right default for a
    traceback, but it means nobody ever sees templates/404.html during
    development and the site looks unfinished when a link is mistyped.

    This re-renders 400/403/404 responses through the matching template. 500 is
    deliberately left alone: with DEBUG on, the traceback is the whole point.

    Controlled by settings.BRANDED_ERROR_PAGES. It is a no-op when DEBUG is
    False, because the real handlers are already doing this.
    """

    # Anything under these prefixes keeps Django's own behaviour: the admin has
    # its own error pages, and a missing static file should stay an obvious 404
    # rather than 40KB of storefront HTML.
    SKIP_PREFIXES = ("/admin/", "/static/", "/media/")

    TEMPLATES = {400: "400.html", 403: "403.html", 404: "404.html"}

    def __init__(self, get_response):
        if not (settings.DEBUG and getattr(settings, "BRANDED_ERROR_PAGES", False)):
            # Tells Django to drop this middleware from the chain entirely.
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        template = self.TEMPLATES.get(response.status_code)
        if template is None:
            return response
        if request.path.startswith(self.SKIP_PREFIXES):
            return response
        # A fetch() from app.js wants JSON or nothing; handing it a full page
        # would break the in-page cart and filter updates.
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return response
        # Only replace Django's own error output. A view that deliberately
        # returns 404 with its own body keeps it.
        if not response.get("Content-Type", "").startswith("text/html"):
            return response
        if getattr(response, "streaming", False):
            return response

        return render(request, template, status=response.status_code)
