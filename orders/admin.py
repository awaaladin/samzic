"""Order management for kitchen staff."""

from django.contrib import admin
from django.utils import timezone

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["line_total"]
    fields = ["food_item", "name", "price", "quantity", "line_total"]
    autocomplete_fields = ["food_item"]

    @admin.display(description="Line total")
    def line_total(self, obj):
        if obj.pk is None:
            return "—"
        return f"₦{obj.total_price:,.2f}"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "full_name",
        "phone_number",
        "total_display",
        "status",
        "payment_status",
        "created_at",
    ]
    list_filter = ["status", "payment_status", "payment_method", "created_at"]
    list_editable = ["status"]
    search_fields = ["reference", "full_name", "phone_number", "email", "user__username"]
    date_hierarchy = "created_at"
    list_select_related = ["user"]
    inlines = [OrderItemInline]
    readonly_fields = ["reference", "user", "created_at", "updated_at", "paid_at"]
    fieldsets = [
        (None, {"fields": ["reference", "user", "status"]}),
        (
            "Delivery details",
            {"fields": ["full_name", "email", "phone_number", "delivery_address", "note"]},
        ),
        (
            "Payment",
            {
                "fields": [
                    "payment_method",
                    "payment_status",
                    "payment_reference",
                    "paid_at",
                ]
            },
        ),
        ("Totals", {"fields": ["subtotal", "delivery_fee", "total_price"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]
    actions = ["mark_confirmed", "mark_delivered", "mark_paid"]

    @admin.display(description="Total", ordering="total_price")
    def total_display(self, obj):
        return f"₦{obj.total_price:,.2f}"

    @admin.action(description="Mark selected orders as confirmed")
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(status=Order.Status.CONFIRMED)
        self.message_user(request, f"{updated} order(s) confirmed.")

    @admin.action(description="Mark selected orders as delivered")
    def mark_delivered(self, request, queryset):
        updated = queryset.update(status=Order.Status.DELIVERED)
        self.message_user(request, f"{updated} order(s) marked delivered.")

    @admin.action(description="Mark selected orders as paid")
    def mark_paid(self, request, queryset):
        # Pay-on-delivery money is collected by the rider, so staff settle it here.
        updated = queryset.update(
            payment_status=Order.PaymentStatus.PAID, paid_at=timezone.now()
        )
        self.message_user(request, f"{updated} order(s) marked paid.")
