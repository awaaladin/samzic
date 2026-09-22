"""Shared read-only aggregates for the console (and the Django admin dashboard,
which delegates here so the two never drift apart).
"""

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone


def dashboard_stats():
    """Cheap aggregate queries only, and guarded by the caller: a missing table
    mid-migration must not lock staff out of the only tool they have to fix it.
    """
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
        "messages_new": ContactMessage.objects.filter(is_handled=False).count(),
        "catering_new": CateringRequest.objects.filter(
            status=CateringRequest.Status.NEW
        ).count(),
        "recent_orders": (
            Order.objects.select_related("user").order_by("-created_at")[:8]
        ),
    }
