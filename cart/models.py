"""Database-backed cart for signed-in customers.

Guests keep using the session cart in ``cart/cart.py``; a signed-in customer
gets one of these so the cart survives a new device or a cleared browser.

``Cart`` deliberately mirrors the session cart's public API — ``add``,
``remove``, ``clear``, iteration, ``len()``, ``rows``, ``distinct_count`` and
``get_total_price`` — so views and templates can hold either object without
knowing which. ``get_cart()`` at the bottom picks the right one.
"""

from decimal import Decimal

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ValidationError
from django.db import models
from django.dispatch import receiver

from menu.models import FoodItem

from .cart import MAX_QUANTITY_PER_ITEM
from .cart import Cart as SessionCart


class Cart(models.Model):
    """A cart persisted in the database, linked one-to-one with a user.

    Created on demand the first time a signed-in customer needs a cart.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart"
    )
    created = models.DateTimeField(auto_now_add=True)

    # Rows are read several times per request (navbar badge, page body, totals),
    # so they are built once. Class-level default; assigning in a method shadows
    # it per instance.
    _rows_cache = None

    def __str__(self):
        return f"Cart for {self.user}"  # pragma: no cover

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def add(self, item, quantity=1, override_quantity=False):
        """Add ``quantity`` of ``item``, or replace the quantity outright.

        Returns the resulting quantity so views can report what happened.
        """
        if not isinstance(item, FoodItem):
            raise ValidationError("Invalid item supplied to Cart.add")
        cart_item, _ = CartItem.objects.get_or_create(
            cart=self, item=item, defaults={"quantity": 0}
        )
        new_quantity = quantity if override_quantity else cart_item.quantity + quantity
        new_quantity = max(1, min(new_quantity, MAX_QUANTITY_PER_ITEM))
        cart_item.quantity = new_quantity
        cart_item.save(update_fields=["quantity"])
        self._rows_cache = None
        return new_quantity

    def remove(self, item):
        """Drop an item from the cart entirely."""
        CartItem.objects.filter(cart=self, item=item).delete()
        self._rows_cache = None

    def clear(self):
        """Empty the cart — called once an order is placed successfully."""
        # Deletes through the relation, not through `rows`: a line that has
        # since sold out is filtered out of `rows` but must still be cleared.
        self.db_items.all().delete()
        self._rows_cache = None

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def _build_rows(self):
        """Rows in the same shape the session cart produces, in one query.

        An item deleted or marked sold out since it was added should not
        silently ride along to checkout, so those lines are filtered out.
        """
        return [
            {
                "item": ci.item,
                "quantity": ci.quantity,
                "unit_price": ci.item.price,
                "total_price": ci.item.price * ci.quantity,
            }
            for ci in self.db_items.select_related("item", "item__category").filter(
                item__available=True, item__category__is_active=True
            )
        ]

    @property
    def rows(self):
        if self._rows_cache is None:
            self._rows_cache = self._build_rows()
        return self._rows_cache

    def __iter__(self):
        yield from self.rows

    def __len__(self):
        """Total number of plates, not the number of distinct dishes."""
        return sum(row["quantity"] for row in self.rows)

    def __bool__(self):
        # Without this, truthiness falls back to __len__ — so a saved cart
        # holding only sold-out lines would read as empty in one place and
        # non-empty in another. Both now agree: no sellable rows means empty.
        return bool(self.rows)

    @property
    def distinct_count(self):
        return len(self.rows)

    def get_total_price(self):
        return sum(
            (row["total_price"] for row in self.rows),
            Decimal("0.00"),
        )


class CartItem(models.Model):
    """One dish and its quantity within a saved cart."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="db_items")
    item = models.ForeignKey(
        FoodItem, on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        # One row per dish per cart; quantity is a field, not extra rows.
        unique_together = ("cart", "item")

    def __str__(self):
        return f"{self.quantity} × {self.item.name}"  # pragma: no cover


def get_cart(request):
    """The cart for this visitor: saved for members, session-only for guests."""
    if request.user.is_authenticated:
        return Cart.objects.get_or_create(user=request.user)[0]
    return SessionCart(request)


@receiver(user_logged_in)
def merge_session_cart(sender, request, user, **kwargs):
    """Carry a guest's basket into their saved cart when they sign in.

    Quantities are added to whatever is already saved, so signing in never
    silently drops a dish the customer picked either side of the login.
    """
    if request is None:
        return

    session_items = request.session.get(settings.CART_SESSION_ID) or {}
    if not session_items:
        return

    db_cart, _ = Cart.objects.get_or_create(user=user)
    wanted = {}
    for item_id, quantity in session_items.items():
        if str(item_id).isdigit():
            wanted[int(item_id)] = quantity

    # One query for the whole basket rather than one per line.
    for item in FoodItem.objects.filter(id__in=wanted):
        db_cart.add(item, quantity=wanted[item.id])

    request.session[settings.CART_SESSION_ID] = {}
    request.session.modified = True
