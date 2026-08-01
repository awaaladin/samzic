"""Session-backed shopping cart.

Only ``{item_id: quantity}`` is stored in the session; prices are read live from
the database on every request. That way a price change in the admin is reflected
immediately instead of a customer checking out at a stale price.
"""

from decimal import Decimal

from django.conf import settings

from menu.models import FoodItem

# Guard rail so a tampered form cannot order 9,999 plates of jollof.
MAX_QUANTITY_PER_ITEM = 20


class Cart:
    """Dict-like wrapper around the cart stored in ``request.session``."""

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if cart is None:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart
        self._items_cache = None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def add(self, item, quantity=1, override_quantity=False):
        """Add ``quantity`` of ``item``, or replace the quantity outright.

        Returns the resulting quantity so views can report what happened.
        """
        item_id = str(item.id)
        current = self.cart.get(item_id, 0)
        new_quantity = quantity if override_quantity else current + quantity
        new_quantity = max(1, min(new_quantity, MAX_QUANTITY_PER_ITEM))
        self.cart[item_id] = new_quantity
        self.save()
        return new_quantity

    def remove(self, item):
        """Drop an item from the cart entirely."""
        item_id = str(item.id)
        if item_id in self.cart:
            del self.cart[item_id]
            self.save()

    def clear(self):
        """Empty the cart — called once an order is placed successfully."""
        self.session[settings.CART_SESSION_ID] = {}
        self.session.modified = True
        self.cart = self.session[settings.CART_SESSION_ID]
        self._items_cache = None

    def save(self):
        self.session.modified = True
        self._items_cache = None

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def _build_rows(self):
        """Join the session quantities against the live menu, in one query."""
        if not self.cart:
            return []

        items = FoodItem.objects.select_related("category").filter(
            id__in=[int(pk) for pk in self.cart if str(pk).isdigit()]
        )
        by_id = {str(item.id): item for item in items}

        rows = []
        stale_ids = []
        for item_id, quantity in self.cart.items():
            item = by_id.get(str(item_id))
            # An item deleted or marked sold out since it was added should not
            # silently ride along to checkout.
            if item is None or not item.available or not item.category.is_active:
                stale_ids.append(item_id)
                continue
            rows.append(
                {
                    "item": item,
                    "quantity": quantity,
                    "unit_price": item.price,
                    "total_price": item.price * quantity,
                }
            )

        if stale_ids:
            for item_id in stale_ids:
                self.cart.pop(item_id, None)
            self.session.modified = True

        return rows

    @property
    def rows(self):
        if self._items_cache is None:
            self._items_cache = self._build_rows()
        return self._items_cache

    def __iter__(self):
        yield from self.rows

    def __len__(self):
        """Total number of plates, not the number of distinct dishes."""
        return sum(row["quantity"] for row in self.rows)

    def __bool__(self):
        return bool(self.rows)

    @property
    def distinct_count(self):
        return len(self.rows)

    def get_total_price(self):
        return sum(
            (row["total_price"] for row in self.rows),
            Decimal("0.00"),
        )
