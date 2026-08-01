"""Admin for enquiries. These lists double as the kitchen's inbox."""

from django.contrib import admin

from .models import CateringRequest, ContactMessage


@admin.register(CateringRequest)
class CateringRequestAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "event_type",
        "guest_count",
        "event_date",
        "status",
        "created_at",
    )
    list_filter = ("status", "event_type", "event_date")
    search_fields = ("full_name", "email", "phone_number", "venue_area")
    list_editable = ("status",)
    date_hierarchy = "event_date"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Contact", {"fields": ("full_name", "email", "phone_number")}),
        (
            "Event",
            {"fields": ("event_type", "guest_count", "event_date", "venue_area")},
        ),
        ("Brief", {"fields": ("menu_ideas",)}),
        ("Pipeline", {"fields": ("status", "created_at", "updated_at")}),
    )

    @admin.action(description="Mark selected requests as quoted")
    def mark_quoted(self, request, queryset):
        updated = queryset.update(status=CateringRequest.Status.QUOTED)
        self.message_user(request, f"{updated} request(s) marked as quoted.")

    actions = ["mark_quoted"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("full_name", "subject", "email", "is_handled", "created_at")
    list_filter = ("is_handled", "subject")
    search_fields = ("full_name", "email", "message")
    list_editable = ("is_handled",)
    readonly_fields = ("created_at", "updated_at")

    @admin.action(description="Mark selected messages as handled")
    def mark_handled(self, request, queryset):
        updated = queryset.update(is_handled=True)
        self.message_user(request, f"{updated} message(s) marked as handled.")

    actions = ["mark_handled"]
