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
