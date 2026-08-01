"""Show delivery details inline on the built-in User admin."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Delivery details"
    fields = ["full_name", "phone_number", "delivery_address"]


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ["username", "email", "full_name", "phone_number", "is_staff"]
    list_select_related = ["profile"]

    @admin.display(description="Full name")
    def full_name(self, obj):
        return getattr(obj.profile, "full_name", "") or "—"

    @admin.display(description="Phone")
    def phone_number(self, obj):
        return getattr(obj.profile, "phone_number", "") or "—"


# Swap the default User admin for the one that carries the profile inline.
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
