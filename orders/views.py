"""Checkout and order history."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Profile
from cart.cart import Cart

from .forms import CheckoutForm
from .models import Order, OrderItem
from .payments import get_gateway
from .services import get_order_totals


@login_required
def checkout(request):
    """Review the order, confirm delivery details, and place it."""
    cart = Cart(request)
    if not cart:
        messages.warning(request, "Your cart is empty — add something tasty first.")
        return redirect("menu:menu")

    profile, _ = Profile.objects.get_or_create(user=request.user)
    totals = get_order_totals(cart.get_total_price())

    if request.method == "POST":
        form = CheckoutForm(request.POST, profile=profile)
        if form.is_valid():
            order = _place_order(request, cart, form, totals)

            gateway = get_gateway(order.payment_method)
            result = gateway.initiate(order, request=request)

            if not result.success:
                # The order row stays as an unpaid record so support can trace it.
                messages.error(
                    request, result.message or "We could not start your payment."
                )
                return redirect("orders:checkout")

            # Only empty the cart once the order is safely written.
            cart.clear()
            request.session["last_order_reference"] = order.reference

            if result.redirect_url:
                # Online gateways (Paystack, later) take over from here.
                return redirect(result.redirect_url)

            messages.success(request, result.message or "Order placed successfully.")
            return redirect("orders:success", reference=order.reference)

        messages.error(request, "Please fix the highlighted fields to continue.")
    else:
        form = CheckoutForm(profile=profile)

    context = {
        "form": form,
        "cart": cart,
        "totals": totals,
        "profile": profile,
    }
    return render(request, "orders/checkout.html", context)


@transaction.atomic
def _place_order(request, cart, form, totals):
    """Write the Order + OrderItem rows as one unit.

    Prices are re-read from the cart rows (which read the live menu), never from
    the submitted form, so a tampered POST cannot set its own price.
    """
    order = form.save(commit=False)
    order.user = request.user
    order.subtotal = totals["subtotal"]
    order.delivery_fee = totals["delivery_fee"]
    order.total_price = totals["total"]
    if not order.email:
        order.email = request.user.email
    order.save()

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                food_item=row["item"],
                name=row["item"].name,
                price=row["unit_price"],
                quantity=row["quantity"],
            )
            for row in cart
        ]
    )
    return order


@login_required
def order_success(request, reference):
    """Confirmation page shown right after checkout."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), reference=reference, user=request.user
    )
    return render(request, "orders/success.html", {"order": order})


@login_required
def order_list(request):
    """The customer's own order history."""
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "orders/list.html", {"orders": orders})


@login_required
def order_detail(request, reference):
    """A single past order. Scoped to the owner — references are not public."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), reference=reference, user=request.user
    )
    return render(request, "orders/detail.html", {"order": order})
