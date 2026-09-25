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


class CacheControlMiddleware:
    """Give every dynamic response an explicit, correct caching policy.

    Every page here carries per-visitor content — the cart badge in the header,
    the signed-in name, flash messages — so none of it may sit in a shared cache
    or be served stale after the visitor changes something:

    * Signed-in / transactional areas (account, cart, checkout, orders, console,
      admin) are ``no-store``: never written to disk or a proxy, and re-fetched on
      back/forward instead of showing yesterday's cart.
    * Everything else is ``private, no-cache``: the browser may keep a copy but
      must revalidate before reusing it, so a menu or price edit shows up on the
      next visit rather than whenever a heuristic expiry lapses.
    * Responses that already chose a policy (a view using ``cache_control``) are
      left alone.

    Static files never reach this: WhiteNoise answers them earlier in the chain
    with its own long-lived headers.
    """

    NO_STORE_PREFIXES = (
        "/console/", "/admin/", "/accounts/", "/cart/", "/orders/", "/checkout",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.utils.cache import add_never_cache_headers, patch_cache_control

        response = self.get_response(request)
        if response.has_header("Cache-Control"):
            return response

        sensitive = request.path.startswith(self.NO_STORE_PREFIXES)
        is_read = request.method in ("GET", "HEAD")
        is_page = response.get("Content-Type", "").startswith("text/html")

        if sensitive or not is_read or not is_page:
            # Writes, redirects, JSON and anything signed-in: never store.
            add_never_cache_headers(response)
        else:
            patch_cache_control(response, private=True, no_cache=True, must_revalidate=True)
        return response


class TurboFormStatusMiddleware:
    """Make invalid form re-renders work with Turbo Drive.

    Turbo submits forms over fetch and only accepts two answers: a redirect
    (success) or a 4xx/5xx page (failure, which it renders in place). Our views
    re-render a form with its errors as a plain ``200``, which Turbo treats as a
    protocol error and ignores — the visitor would see nothing happen.

    Turbo announces itself with ``text/vnd.turbo-stream.html`` in ``Accept`` on form
    submissions, so a ``200`` HTML answer to such a POST is a validation failure and
    is re-labelled ``422``. Browsers (and app.js's own fetches) never send that
    header, so ordinary form posts and JSON calls are untouched.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method == "POST"
            and response.status_code == 200
            and "text/vnd.turbo-stream.html" in request.headers.get("Accept", "")
            and response.get("Content-Type", "").startswith("text/html")
        ):
            response.status_code = 422
        return response
