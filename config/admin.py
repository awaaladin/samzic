"""Branded admin site for Samzic Foods Empire.

This subclasses Django's own AdminSite rather than replacing it. Everything the
default admin does still works — permissions, add/change/delete, inlines, bulk
actions, history, search, filters — because the ModelAdmin classes in each app
are untouched. What changes is the skin (templates/admin/) and the landing page.

This is now the *fallback* surface: staff land on the console (see the
`console` app) day to day, and drop down here for anything the console
doesn't cover yet — permissions, bulk actions, raw model editing.

Wired in via config.apps.SamzicAdminConfig, which replaces
django.contrib.admin in INSTALLED_APPS. That keeps every @admin.register
decorator working as-is.
"""

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from console.services import dashboard_stats


class SamzicAdminSite(admin.AdminSite):
    site_header = "Samzic Foods Empire"
    site_title = "Samzic admin"
    index_title = "Kitchen dashboard"
    # Shown on the login screen and in the breadcrumb back-link.
    site_url = "/"
    # Not "admin/index.html": that path would shadow the template it extends
    # and recurse, since templates/ is searched before Django's own.
    index_template = "admin/samzic_index.html"

    def login(self, request, extra_context=None):
        """The one staff sign-in gate (this branded admin/login.html) lands on
        the console by default — not the Django admin dashboard — since the
        console is the day-to-day surface. An explicit ?next= (e.g. the
        console's own staff_required redirect) always wins over this default,
        so a visit to a specific admin page you're not logged in for still
        returns you there afterwards, same as before.
        """
        console = reverse("console:dashboard")
        admin_index = reverse("admin:index", current_app=self.name)

        # Django itself sends signed-out visitors of /admin/ to
        # /admin/login/?next=/admin/. That "next" is not a real preference (it is
        # just where they happened to knock), so it must not beat the console.
        # Deeper admin URLs (a specific change form) are kept as-is.
        if request.method == "GET" and request.GET.get("next") == admin_index:
            return HttpResponseRedirect(f"{request.path}?next={console}")
        if request.method == "POST" and admin_index in (
            request.POST.get("next"),
            request.GET.get("next"),
        ):
            request.POST = request.POST.copy()
            request.POST["next"] = console

        if request.method == "GET" and self.has_permission(request):
            target = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(
                target, allowed_hosts={request.get_host()}
            ):
                target = console
            return HttpResponseRedirect(target)

        context = {**(extra_context or {})}
        if "next" not in request.GET and "next" not in request.POST:
            context["next"] = console
        return super().login(request, extra_context=context)

    def each_context(self, request):
        """Add dashboard figures to every admin page's context.

        Cheap aggregate queries only, and guarded: the admin must still load if
        a table is missing mid-migration, otherwise a half-applied deploy locks
        staff out of the only tool they have to fix it.
        """
        context = super().each_context(request)
        try:
            context["dashboard"] = dashboard_stats()
        except Exception:  # noqa: BLE001 - a broken stat must not break the admin
            context["dashboard"] = None
        return context
