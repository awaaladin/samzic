"""App config that installs the branded admin site.

Listing "config.apps.SamzicAdminConfig" in INSTALLED_APPS instead of
"django.contrib.admin" makes django.contrib.admin.site point at
SamzicAdminSite. Every existing @admin.register decorator then registers
against it with no other changes.
"""

from django.contrib.admin.apps import AdminConfig


class SamzicAdminConfig(AdminConfig):
    default_site = "config.admin.SamzicAdminSite"
