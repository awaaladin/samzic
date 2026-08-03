"""Root URL configuration for Samzic Foods Empire."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.templatetags.static import static as static_url

from . import views

# Titles now live on SamzicAdminSite in config/admin.py, so they apply to the
# login page too rather than only after the site module is imported.

urlpatterns = [
    path("admin/control-room/", views.control_room, name="admin_control_room"),
    path("admin/", admin.site.urls),
    path("control-room/", views.control_room, name="control_room"),
    path("account/", RedirectView.as_view(pattern_name="accounts:profile", permanent=False), name="account_dashboard"),
    path("dashboard/", RedirectView.as_view(pattern_name="accounts:profile", permanent=False), name="dashboard"),
    # Browsers request /favicon.ico from the domain root regardless of the
    # <link> tags, so point that at the real file instead of serving a 404.
    path(
        "favicon.ico",
        RedirectView.as_view(url=static_url("favicon.ico"), permanent=True),
    ),
    path("accounts/", include("accounts.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),
    path("", include("pages.urls")),
    # menu owns "/" and "/menu/", so it is registered last.
    path("", include("menu.urls")),
]

# Custom error views (used when DEBUG=False).
handler400 = "config.views.bad_request"
handler403 = "config.views.permission_denied"
handler404 = "config.views.page_not_found"
handler500 = "config.views.server_error"

if settings.DEBUG:
    # Serve uploaded images from MEDIA_ROOT during development only.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
