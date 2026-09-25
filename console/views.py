"""The console: a purpose-built staff surface, separate from django.contrib.admin.

Every view here is read/write against the same models the Django admin edits —
there is one database, not two — but the templates, layout and navigation are
our own (templates/console/), not admin/ templates restyled. The Django admin
stays reachable (see the "Django admin" link in the console sidebar) for
anything not covered here yet: users, groups, permissions, raw model editing,
the builder app, full change history.
"""

import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from menu.models import Category, FoodItem
from orders.forms import OrderMessageForm
from orders.models import Order, OrderMessage
from pages.models import CateringPackage, CateringRequest, ContactMessage

from . import analytics
from .forms import (
    CategoryForm,
    CateringPackageForm,
    CateringStatusForm,
    ContactHandledForm,
    FoodItemForm,
    OrderStatusForm,
)
from .services import dashboard_stats

PAGE_SIZE = 20


def staff_required(view_func):
    """Anonymous visitors go to the branded staff sign-in (admin:login, not the
    customer accounts:login) with ?next= back to the page they wanted; signed-in
    non-staff get a plain 403 rather than a redirect loop back to a login
    they've already used.
    """

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=reverse("admin:login"))
        if not request.user.is_staff:
            raise PermissionDenied("This page is for staff accounts only.")
        return view_func(request, *args, **kwargs)

    return wrapped


def _paginate(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


@staff_required
def dashboard(request):
    try:
        stats = dashboard_stats()
    except Exception:  # noqa: BLE001 - a broken stat must not block the console
        stats = None
    return render(request, "console/dashboard.html", {"stats": stats})


# --- Orders ---------------------------------------------------------------

@staff_required
def order_list(request):
    orders = (
        Order.objects.select_related("user")
        .annotate(
            unread=Count(
                "messages",
                filter=Q(messages__sender=OrderMessage.Sender.CUSTOMER, messages__is_read=False),
            )
        )
        .order_by("-created_at")
    )

    status = request.GET.get("status", "")
    if status:
        orders = orders.filter(status=status)

    q = request.GET.get("q", "").strip()
    if q:
        orders = orders.filter(
            Q(reference__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone_number__icontains=q)
        )

    context = {
        "page_obj": _paginate(request, orders),
        "status_choices": Order.Status.choices,
        "status": status,
        "q": q,
    }
    return render(request, "console/order_list.html", context)


@staff_required
def order_detail(request, reference):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items"),
        reference=reference,
    )
    if request.method == "POST":
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f"Order {order.reference} updated.")
            return redirect("console:order_detail", reference=order.reference)
    else:
        form = OrderStatusForm(instance=order)
        # Opening the order is what "read" means for the kitchen.
        order.messages.filter(sender=OrderMessage.Sender.CUSTOMER, is_read=False).update(is_read=True)

    context = {
        "order": order,
        "form": form,
        "thread": order.messages.select_related("author"),
        "reply_form": OrderMessageForm(),
    }
    return render(request, "console/order_detail.html", context)


@require_POST
@staff_required
def order_reply(request, reference):
    """The kitchen answers a customer's note about this order."""
    order = get_object_or_404(Order, reference=reference)
    form = OrderMessageForm(request.POST)
    if not form.is_valid():
        messages.error(request, " ".join(form.errors.get("body", ["Write a reply first."])))
    elif order.messages.count() >= OrderMessage.MAX_PER_ORDER:
        messages.error(request, "This thread is full \u2014 call the customer instead.")
    else:
        OrderMessage.objects.create(
            order=order,
            sender=OrderMessage.Sender.KITCHEN,
            author=request.user,
            body=form.cleaned_data["body"],
        )
        messages.success(request, f"Reply sent to {order.full_name}.")
    return redirect(f"{reverse('console:order_detail', args=[order.reference])}#kitchen")


@staff_required
def kitchen_inbox(request):
    """Every order with a message thread, unread first \u2014 the kitchen's to-do list."""
    threads = (
        Order.objects.filter(messages__isnull=False)
        .annotate(
            total=Count("messages", distinct=True),
            unread=Count(
                "messages",
                filter=Q(messages__sender=OrderMessage.Sender.CUSTOMER, messages__is_read=False),
                distinct=True,
            ),
        )
        .select_related("user")
    )
    show = request.GET.get("show", "all")
    if show == "unread":
        threads = threads.filter(unread__gt=0)
    threads = list(threads)
    latest = {
        m.order_id: m
        for m in OrderMessage.objects.filter(order__in=threads).order_by("created_at")
    }
    for t in threads:
        t.latest = latest.get(t.pk)
    # Unread first, then most recent activity.
    threads.sort(key=lambda t: (t.unread == 0, -(t.latest.created_at.timestamp() if t.latest else 0)))

    return render(request, "console/kitchen_inbox.html", {"threads": threads, "show": show})


# --- Menu: categories -------------------------------------------------------

@staff_required
def category_list(request):
    categories = Category.objects.order_by("display_order", "name")
    return render(request, "console/category_list.html", {"categories": categories})


@staff_required
def category_form_view(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved “{form.instance.name}”.")
            return redirect("console:categories")
    else:
        form = CategoryForm(instance=category)

    return render(
        request,
        "console/category_form.html",
        {"form": form, "category": category},
    )


@require_POST
@staff_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.food_items.exists():
        messages.error(
            request,
            f"“{category.name}” still has menu items in it — move or delete those first.",
        )
    else:
        name = category.name
        category.delete()
        messages.success(request, f"Deleted “{name}”.")
    return redirect("console:categories")


# --- Menu: food items --------------------------------------------------------

@staff_required
def food_item_list(request):
    items = FoodItem.objects.select_related("category").order_by("-is_featured", "name")

    category_id = request.GET.get("category", "")
    if category_id:
        items = items.filter(category_id=category_id)

    q = request.GET.get("q", "").strip()
    if q:
        items = items.filter(Q(name__icontains=q) | Q(description__icontains=q))

    context = {
        "page_obj": _paginate(request, items),
        "categories": Category.objects.order_by("display_order", "name"),
        "category_id": category_id,
        "q": q,
    }
    return render(request, "console/food_item_list.html", context)


@staff_required
def food_item_form_view(request, pk=None):
    item = get_object_or_404(FoodItem, pk=pk) if pk else None
    if request.method == "POST":
        form = FoodItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved “{form.instance.name}”.")
            return redirect("console:food_items")
    else:
        form = FoodItemForm(instance=item)

    return render(
        request,
        "console/food_item_form.html",
        {"form": form, "item": item},
    )


@require_POST
@staff_required
def food_item_delete(request, pk):
    item = get_object_or_404(FoodItem, pk=pk)
    name = item.name
    item.delete()
    messages.success(request, f"Deleted “{name}”.")
    return redirect("console:food_items")


# --- Marketing: catering leads ----------------------------------------------

@staff_required
def catering_list(request):
    leads = CateringRequest.objects.order_by("-created_at")
    status = request.GET.get("status", "")
    if status:
        leads = leads.filter(status=status)

    context = {
        "page_obj": _paginate(request, leads),
        "status_choices": CateringRequest.Status.choices,
        "status": status,
    }
    return render(request, "console/catering_list.html", context)


@staff_required
def catering_detail(request, pk):
    lead = get_object_or_404(CateringRequest, pk=pk)
    if request.method == "POST":
        form = CateringStatusForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, "Lead updated.")
            return redirect("console:catering_detail", pk=lead.pk)
    else:
        form = CateringStatusForm(instance=lead)

    return render(request, "console/catering_detail.html", {"lead": lead, "form": form})


# --- Marketing: contact messages --------------------------------------------

@staff_required
def message_list(request):
    inbox = ContactMessage.objects.order_by("is_handled", "-created_at")
    return render(request, "console/message_list.html", {"page_obj": _paginate(request, inbox)})


@staff_required
def message_detail(request, pk):
    message_obj = get_object_or_404(ContactMessage, pk=pk)
    if request.method == "POST":
        form = ContactHandledForm(request.POST, instance=message_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Message updated.")
            return redirect("console:message_detail", pk=message_obj.pk)
    else:
        form = ContactHandledForm(instance=message_obj)

    return render(
        request,
        "console/message_detail.html",
        {"message_obj": message_obj, "form": form},
    )


# --- Marketing: catering packages ---------------------------------------------

@staff_required
def package_list(request):
    packages = CateringPackage.objects.order_by("display_order", "name")
    return render(request, "console/package_list.html", {"packages": packages})


@staff_required
def package_form_view(request, pk=None):
    package = get_object_or_404(CateringPackage, pk=pk) if pk else None
    if request.method == "POST":
        form = CateringPackageForm(request.POST, instance=package)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved \u201c{form.instance.name}\u201d \u2014 the catering page is updated.")
            return redirect("console:packages")
    else:
        form = CateringPackageForm(instance=package)
    return render(request, "console/package_form.html", {"form": form, "package": package})


@require_POST
@staff_required
def package_delete(request, pk):
    package = get_object_or_404(CateringPackage, pk=pk)
    name = package.name
    package.delete()
    messages.success(request, f"Deleted \u201c{name}\u201d.")
    return redirect("console:packages")


# --- Insights: orders and revenue ---------------------------------------------

def _insight_context(request, data):
    """Everything the two insight templates share: the data plus the option lists
    for their filter bars."""
    return {
        "d": data,
        "period_choices": analytics.PERIOD_CHOICES,
        "range_choices": analytics.RANGE_CHOICES,
        "chart_choices": analytics.CHART_CHOICES,
        "query": request.GET.urlencode(),
    }


@staff_required
def order_insights(request):
    data = analytics.order_insights(request.GET)
    context = _insight_context(request, data)
    context.update({
        "status_choices": Order.Status.choices,
        "payment_status_choices": Order.PaymentStatus.choices,
    })
    return render(request, "console/order_insights.html", context)


@staff_required
def revenue(request):
    data = analytics.revenue_insights(request.GET)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="samzic-revenue-{data["start"]}-to-{data["end"]}.csv"'
        )
        response.write("\ufeff")  # so Excel reads the file as UTF-8
        writer = csv.writer(response)
        writer.writerow([
            "Date", "Reference", "Customer", "Phone", "Payment method", "Payment status",
            "Order status", "Subtotal", "Delivery fee", "Total", "Payment reference",
        ])
        for o in data["ledger"].iterator():
            writer.writerow([
                o.money_date.strftime("%Y-%m-%d %H:%M"), o.reference, o.full_name, o.phone_number,
                o.get_payment_method_display(), o.get_payment_status_display(),
                o.get_status_display(), o.subtotal, o.delivery_fee, o.total_price, o.payment_reference,
            ])
        return response

    context = _insight_context(request, data)
    context.update({
        "view_choices": analytics.REVENUE_VIEWS,
        "method_choices": Order.PaymentMethod.choices,
        "page_obj": _paginate(request, data["ledger"]),
    })
    return render(request, "console/revenue.html", context)
