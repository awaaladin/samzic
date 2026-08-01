"""Cart views. Every mutation is POST-only so it is CSRF protected.

Each mutation answers one of two ways:

* a normal form post gets a redirect and a Django flash message, so the site
  works with JavaScript switched off;
* a ``fetch`` sending ``X-Requested-With: XMLHttpRequest`` gets JSON with the
  new totals, so the page can update in place without a reload.

The branch is only in the response — the cart logic above it runs identically.
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from menu.models import FoodItem
from orders.services import get_order_totals

from .cart import MAX_QUANTITY_PER_ITEM, Cart
from .forms import AddToCartForm


def _wants_json(request):
    """True when the request came from our fetch() helper rather than a form."""
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _redirect_back(request, default="cart:detail"):
    """Send the customer back where they came from after adding an item."""
    next_url = request.POST.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(default)


def _cart_payload(request, cart, message="", level="success"):
    """The JSON body every in-page cart mutation returns.

    Includes the rendered summary block so the cart page's totals, delivery
    line and free-delivery notice stay in one template instead of being
    rebuilt in JavaScript.
    """
    totals = get_order_totals(cart.get_total_price())
    payload = {
        "ok": True,
        "message": message,
        "level": level,
        "count": len(cart),
        "distinct_count": cart.distinct_count,
        "empty": not cart,
        "totals": {
            "subtotal": f"{totals['subtotal']:,.2f}",
            "delivery_fee": f"{totals['delivery_fee']:,.2f}",
            "total": f"{totals['total']:,.2f}",
            "free_delivery": totals["qualifies_for_free_delivery"],
        },
        "rows": {
            str(row["item"].id): {
                "quantity": row["quantity"],
                "line_total": f"{row['total_price']:,.0f}",
            }
            for row in cart
        },
    }
    # Only the cart page needs the re-rendered summary; skip the work elsewhere.
    if request.POST.get("with_summary"):
        payload["summary_html"] = render_to_string(
            "cart/_summary.html",
            {"cart": cart, "totals": totals, "max_quantity": MAX_QUANTITY_PER_ITEM},
            request=request,
        )
    return payload


def _error(request, message, redirect_to="cart:detail"):
    """Report a failed mutation the right way for the caller."""
    if _wants_json(request):
        return JsonResponse({"ok": False, "message": message, "level": "error"}, status=400)
    messages.error(request, message)
    return redirect(redirect_to)


def cart_detail(request):
    """The cart page: line items, totals and the link to checkout."""
    cart = Cart(request)
    return render(
        request,
        "cart/detail.html",
        {
            "cart": cart,
            "totals": get_order_totals(cart.get_total_price()),
            # Lets the template disable "+" at the ceiling rather than letting
            # the customer post a quantity the form will only reject.
            "max_quantity": MAX_QUANTITY_PER_ITEM,
        },
    )


@require_POST
def cart_add(request, item_id):
    """Add (or set) a quantity for one dish."""
    cart = Cart(request)
    item = get_object_or_404(FoodItem.objects.select_related("category"), id=item_id)

    if not item.available or not item.category.is_active:
        return _error(request, f"Sorry, {item.name} is sold out right now.", "menu:menu")

    form = AddToCartForm(request.POST)
    if not form.is_valid():
        return _error(request, "Please choose a valid quantity.")

    quantity = cart.add(
        item,
        quantity=form.cleaned_data["quantity"],
        override_quantity=form.cleaned_data["override"],
    )
    message = f"{item.name} × {quantity} is in your cart."

    if _wants_json(request):
        return JsonResponse(_cart_payload(request, cart, message))

    messages.success(request, message)
    return _redirect_back(request)


@require_POST
def cart_update(request, item_id):
    """Set an exact quantity from the cart page."""
    cart = Cart(request)
    item = get_object_or_404(FoodItem, id=item_id)

    form = AddToCartForm(request.POST)
    if not form.is_valid():
        return _error(request, f"Please enter a quantity between 1 and {MAX_QUANTITY_PER_ITEM}.")

    quantity = cart.add(item, quantity=form.cleaned_data["quantity"], override_quantity=True)
    message = f"Updated {item.name} to {quantity}."

    if _wants_json(request):
        return JsonResponse(_cart_payload(request, cart, message))

    messages.success(request, message)
    return redirect("cart:detail")


@require_POST
def cart_remove(request, item_id):
    cart = Cart(request)
    item = get_object_or_404(FoodItem, id=item_id)
    cart.remove(item)
    message = f"{item.name} removed from your cart."

    if _wants_json(request):
        payload = _cart_payload(request, cart, message, level="info")
        payload["removed_id"] = str(item.id)
        return JsonResponse(payload)

    messages.info(request, message)
    return redirect("cart:detail")


@require_POST
def cart_clear(request):
    cart = Cart(request)
    cart.clear()
    message = "Your cart is now empty."

    if _wants_json(request):
        return JsonResponse(_cart_payload(request, cart, message, level="info"))

    messages.info(request, message)
    return redirect("cart:detail")
