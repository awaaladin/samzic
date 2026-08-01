"""Orders and their line items.

Two deliberate decisions:

* ``OrderItem`` copies the dish name and price at purchase time. Menu prices
  change; an order is a historical record and must not change with them.
* ``Order.food_item`` uses ``SET_NULL`` so removing a dish from the menu never
  destroys past orders.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


def generate_reference():
    """Short, human-readable, unguessable order reference (e.g. SFE-7K3QD9)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alike characters
    return "SFE-" + "".join(secrets.choice(alphabet) for _ in range(6))


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        # Keys must match the gateway keys in orders/payments.py.
        PAY_ON_DELIVERY = "pod", "Pay on Delivery"
        # PAYSTACK = "paystack", "Pay now with card (Paystack)"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    reference = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # keep the order history even if staff prune users
        related_name="orders",
    )

    # Snapshot of the delivery details, copied from the profile at checkout so a
    # later profile edit cannot rewrite where an old order was sent.
    full_name = models.CharField(max_length=140)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20)
    delivery_address = models.TextField()
    note = models.TextField(blank=True, help_text="Rider instructions from the customer.")

    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PAY_ON_DELIVERY
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    payment_reference = models.CharField(
        max_length=120, blank=True, help_text="Gateway transaction id, when applicable."
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.full_name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            reference = generate_reference()
            # Collisions are vanishingly unlikely but cheap to rule out.
            while Order.objects.filter(reference=reference).exists():
                reference = generate_reference()
            self.reference = reference
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("orders:detail", kwargs={"reference": self.reference})

    @property
    def item_count(self):
        return sum(line.quantity for line in self.items.all())

    @property
    def status_trail(self):
        """Timeline of statuses for the order detail page.

        Each step shows (label, reached), where reached is True if the order
        passed that milestone. Cancelled orders short-circuit the normal flow.
        """
        if self.status == self.Status.CANCELLED:
            return [
                ("Order placed", True),
                ("Cancelled", True),
            ]

        return [
            ("Order placed", True),
            ("Kitchen confirmed", self.status in [self.Status.CONFIRMED, self.Status.DELIVERED]),
            ("Out for delivery", self.status == self.Status.DELIVERED),
            ("Delivered", self.status == self.Status.DELIVERED),
        ]

    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID

    def mark_paid(self, reference=""):
        """Called by staff for cash orders, or by a gateway callback later."""
        self.payment_status = self.PaymentStatus.PAID
        self.paid_at = timezone.now()
        if reference:
            self.payment_reference = reference
        self.save(update_fields=["payment_status", "paid_at", "payment_reference", "updated_at"])

    def recalculate_totals(self, save=True):
        """Re-derive the money fields from the current line items."""
        self.subtotal = sum(
            (line.total_price for line in self.items.all()), Decimal("0.00")
        )
        self.total_price = self.subtotal + self.delivery_fee
        if save:
            self.save(update_fields=["subtotal", "total_price", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food_item = models.ForeignKey(
        "menu.FoodItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    # Historical snapshot — never read the live FoodItem for these.
    name = models.CharField(max_length=140)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} × {self.name}"

    @property
    def total_price(self):
        return self.price * self.quantity
