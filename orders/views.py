"""Checkout and order history."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import Profile
from cart.models import get_cart

from django.views.decorators.http import require_POST

from .forms import CheckoutForm, OrderMessageForm
from .models import Order, OrderItem, OrderMessage
from .payments import get_gateway
from .services import get_order_totals


@login_required
def checkout(request):
    """Review the order, confirm delivery details, and place it."""
    cart = get_cart(request)
    if not cart:
        messages.warning(request, "Your cart is empty — add something tasty first.")
        return redirect("menu:menu")

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.is_complete:
        # Checkout is prefilled from the account page, so the account has to be
        # filled in first. `next` brings the customer straight back afterwards.
        messages.info(
            request,
            "Complete your name, phone number and delivery address so we can "
            "fill in checkout for you.",
        )
        return redirect(f"{reverse('accounts:profile')}?next={reverse('orders:checkout')}")
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
        .annotate(
            unread_replies=Count(
                "messages",
                filter=Q(messages__sender=OrderMessage.Sender.KITCHEN, messages__is_read=False),
            )
        )
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "orders/list.html", {"orders": orders})


# Statuses where the kitchen can still act on a message. Once an order is
# delivered or cancelled the thread stays readable but closes to new messages.
MESSAGEABLE_STATUSES = (Order.Status.PENDING, Order.Status.CONFIRMED)


@login_required
def order_detail(request, reference):
    """A single past order. Scoped to the owner — references are not public."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), reference=reference, user=request.user
    )
    # Opening the page is what "read" means: the kitchen's replies stop counting
    # as unread for this customer.
    order.messages.filter(sender=OrderMessage.Sender.KITCHEN, is_read=False).update(is_read=True)

    context = {
        "order": order,
        "thread": order.messages.select_related("author"),
        "message_form": OrderMessageForm(),
        "can_message": order.status in MESSAGEABLE_STATUSES,
    }
    return render(request, "orders/detail.html", context)


@login_required
@require_POST
def order_message(request, reference):
    """Send a note to the kitchen about this order."""
    order = get_object_or_404(Order, reference=reference, user=request.user)
    back = redirect(f"{reverse('orders:detail', args=[order.reference])}#kitchen")

    if order.status not in MESSAGEABLE_STATUSES:
        messages.error(request, "This order is closed, so it can't take new messages. Call us if something is wrong.")
        return back
    if order.messages.count() >= OrderMessage.MAX_PER_ORDER:
        messages.error(request, "This order's message thread is full. Please call us instead.")
        return back

    form = OrderMessageForm(request.POST)
    if form.is_valid():
        OrderMessage.objects.create(
            order=order,
            sender=OrderMessage.Sender.CUSTOMER,
            author=request.user,
            body=form.cleaned_data["body"],
        )
        messages.success(request, "Sent to the kitchen — they will reply here.")
    else:
        messages.error(request, " ".join(form.errors.get("body", ["Please write a message."])))
    return back
