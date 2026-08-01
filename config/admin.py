"""Branded admin site for Samzic Foods Empire.

This subclasses Django's own AdminSite rather than replacing it. Everything the
default admin does still works — permissions, add/change/delete, inlines, bulk
actions, history, search, filters — because the ModelAdmin classes in each app
are untouched. What changes is the skin (templates/admin/) and the landing page,
which gets the numbers whoever runs the kitchen actually opens the admin to see.

Wired in via config.apps.SamzicAdminConfig, which replaces
django.contrib.admin in INSTALLED_APPS. That keeps every @admin.register
decorator working as-is.
"""

from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Sum
from django.utils import timezone


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
            context["dashboard"] = self.dashboard_stats()
        except Exception:  # noqa: BLE001 - a broken stat must not break the admin
            context["dashboard"] = None
        return context

    def dashboard_stats(self):
        from menu.models import Category, FoodItem
        from orders.models import Order
        from pages.models import CateringRequest, ContactMessage

        today = timezone.localdate()
        week_ago = timezone.now() - timedelta(days=7)

        revenue = Order.objects.filter(
            payment_status=Order.PaymentStatus.PAID
        ).aggregate(total=Sum("total_price"))["total"]

        by_status = {
            row["status"]: row["n"]
            for row in Order.objects.values("status").annotate(n=Count("id"))
        }

        return {
            "orders_today": Order.objects.filter(created_at__date=today).count(),
            "orders_week": Order.objects.filter(created_at__gte=week_ago).count(),
            "orders_pending": by_status.get(Order.Status.PENDING, 0),
            "orders_confirmed": by_status.get(Order.Status.CONFIRMED, 0),
            "orders_delivered": by_status.get(Order.Status.DELIVERED, 0),
            "revenue_paid": revenue or 0,
            "unpaid_count": Order.objects.filter(
                payment_status=Order.PaymentStatus.UNPAID
            ).count(),
            "food_total": FoodItem.objects.count(),
            "food_sold_out": FoodItem.objects.filter(available=False).count(),
            "category_total": Category.objects.count(),
            # The two inboxes, so nothing sits unanswered unnoticed.
            "messages_new": ContactMessage.objects.filter(is_handled=False).count(),
            "catering_new": CateringRequest.objects.filter(
                status=CateringRequest.Status.NEW
            ).count(),
            "recent_orders": (
                Order.objects.select_related("user").order_by("-created_at")[:8]
            ),
        }
