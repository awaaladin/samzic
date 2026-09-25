"""Numbers the console sidebar shows next to its links."""


def badges(request):
    """Unread counts for the sidebar. Only computed inside the console, for staff:
    every other page on the site would pay a query for a number it never shows."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_staff):
        return {}
    if not request.path.startswith("/console/"):
        return {}

    from orders.models import OrderMessage
    from pages.models import CateringRequest, ContactMessage

    try:
        return {
            "console_badges": {
                "kitchen": OrderMessage.objects.filter(
                    sender=OrderMessage.Sender.CUSTOMER, is_read=False
                ).count(),
                "messages": ContactMessage.objects.filter(is_handled=False).count(),
                "catering": CateringRequest.objects.filter(
                    status=CateringRequest.Status.NEW
                ).count(),
            }
        }
    except Exception:  # noqa: BLE001 - a sidebar number must never break a page
        return {}
