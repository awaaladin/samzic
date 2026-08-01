"""Payment gateways.

Right now there is exactly one option — Pay on Delivery — but checkout talks to
this module through :func:`get_gateway`, never to a gateway class directly. That
is the seam for Paystack.

Adding Paystack later
---------------------
1. ``pip install requests`` (already listed, commented, in requirements.txt).
2. Put ``PAYSTACK_PUBLIC_KEY`` / ``PAYSTACK_SECRET_KEY`` in ``.env`` and read
   them in ``config/settings.py``.
3. Uncomment ``PaystackGateway`` below and fill in ``initiate``: call
   ``https://api.paystack.co/transaction/initialize`` with the order total in
   *kobo* (``int(order.total_price * 100)``) and return
   ``PaymentResult(redirect_url=<authorization_url>)``.
4. Add a webhook/callback view that verifies the transaction, then calls
   ``order.mark_paid()``.
5. Register it in ``GATEWAYS`` and add its key to
   ``Order.PaymentMethod`` — the checkout form builds its radio buttons from
   those choices, so the new option appears with no template change.

Nothing else in the codebase needs to know a second gateway exists.
"""

from dataclasses import dataclass


@dataclass
class PaymentResult:
    """What a gateway hands back to the checkout view."""

    success: bool = True
    # Set by online gateways; the view redirects here instead of to the
    # success page. ``None`` means "payment is settled offline, carry on".
    redirect_url: str | None = None
    message: str = ""
    reference: str = ""


class BaseGateway:
    """Interface every payment method implements."""

    key = ""
    label = ""
    #: When True the order is only fulfilled after the gateway confirms payment.
    requires_online_payment = False

    def initiate(self, order, request=None):  # pragma: no cover - interface
        raise NotImplementedError


class PayOnDeliveryGateway(BaseGateway):
    """No money moves online: the rider collects cash/transfer at the door."""

    key = "pod"
    label = "Pay on Delivery"
    requires_online_payment = False

    def initiate(self, order, request=None):
        # Deliberately a no-op. The order sits as PENDING until the kitchen
        # confirms it, and payment is recorded by staff after delivery.
        return PaymentResult(
            success=True,
            message="Your order is placed. Please have the exact amount ready for the rider.",
            reference=order.reference,
        )


# class PaystackGateway(BaseGateway):
#     """Card/bank payment via Paystack. See the module docstring for the steps."""
#
#     key = "paystack"
#     label = "Pay now with card (Paystack)"
#     requires_online_payment = True
#
#     def initiate(self, order, request=None):
#         import requests
#         from django.conf import settings
#         from django.urls import reverse
#
#         callback_url = request.build_absolute_uri(
#             reverse("orders:paystack_callback", kwargs={"reference": order.reference})
#         )
#         response = requests.post(
#             "https://api.paystack.co/transaction/initialize",
#             headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
#             json={
#                 "email": order.email,
#                 "amount": int(order.total_price * 100),  # Paystack works in kobo
#                 "reference": order.reference,
#                 "callback_url": callback_url,
#             },
#             timeout=15,
#         )
#         payload = response.json()
#         if not payload.get("status"):
#             return PaymentResult(success=False, message=payload.get("message", "Payment failed."))
#         return PaymentResult(
#             success=True,
#             redirect_url=payload["data"]["authorization_url"],
#             reference=order.reference,
#         )


GATEWAYS = {
    PayOnDeliveryGateway.key: PayOnDeliveryGateway(),
    # PaystackGateway.key: PaystackGateway(),
}


def get_gateway(key):
    """Look up a gateway, falling back to Pay on Delivery."""
    return GATEWAYS.get(key) or GATEWAYS[PayOnDeliveryGateway.key]
