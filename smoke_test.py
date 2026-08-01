"""Throwaway smoke test — exercises every page and the full order flow.

Not part of the app; delete after verifying. Run:
    ./.venv/Scripts/python.exe smoke_test.py
"""

import os
from datetime import date, timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

# Django's test runner normally does this for us; a standalone script has to ask.
# It appends "testserver" to ALLOWED_HOSTS (otherwise every request 400s) and
# routes email to locmem so nothing is actually sent.
setup_test_environment()

from menu.models import FoodItem  # noqa: E402
from orders.models import Order  # noqa: E402
from pages.models import CateringRequest, ContactMessage  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


client = Client()
item = FoodItem.objects.available().first()
print(f"Using item: {item.name} (#{item.id}) @ {item.price}\n")

# Read the slug from the database rather than hardcoding it — the seeded
# category set is free to change without breaking this test.
category_slug = item.category.slug

# --- Anonymous browsing -----------------------------------------------------
print("== Anonymous pages ==")
for label, url in [
    ("home", "/"),
    ("menu", "/menu/"),
    (f"menu?category={category_slug}", f"/menu/?category={category_slug}"),
    ("menu?q", "/menu/?q=jollof"),
    ("menu?page=2", "/menu/?page=2"),
    ("menu?category=bogus", "/menu/?category=no-such-category"),
    ("food detail", item.get_absolute_url()),
    ("cart (empty)", "/cart/"),
    ("about", "/about/"),
    ("catering", "/catering/"),
    ("contact", "/contact/"),
    ("login", "/accounts/login/"),
    ("signup", "/accounts/signup/"),
]:
    response = client.get(url)
    check(f"GET {label}", response.status_code == 200, f"got {response.status_code}")

check("GET 404 page", client.get("/no-such-page/").status_code == 404)
check(
    "checkout redirects anonymous",
    client.get("/orders/checkout/").status_code == 302,
)

# --- Cart -------------------------------------------------------------------
print("\n== Cart ==")
response = client.post(f"/cart/add/{item.id}/", {"quantity": 2}, follow=True)
check("POST add to cart", response.status_code == 200)
check("cart badge shows 2", response.context["cart"].__len__() == 2,
      f"got {len(response.context['cart'])}")

response = client.post(f"/cart/update/{item.id}/", {"quantity": 3}, follow=True)
check("POST update quantity", len(response.context["cart"]) == 3,
      f"got {len(response.context['cart'])}")

response = client.get("/cart/")
totals = response.context["totals"]
expected_subtotal = item.price * 3
check("subtotal correct", totals["subtotal"] == expected_subtotal,
      f"{totals['subtotal']} != {expected_subtotal}")
check("total = subtotal + delivery",
      totals["total"] == totals["subtotal"] + totals["delivery_fee"])

check("GET add is rejected (POST-only)",
      client.get(f"/cart/add/{item.id}/").status_code == 405)

# --- Signup + profile -------------------------------------------------------
print("\n== Accounts ==")
User.objects.filter(username="smoketester").delete()
response = client.post(
    "/accounts/signup/",
    {
        "username": "smoketester",
        "email": "smoke@example.com",
        "password1": "TastyJollof2026!",
        "password2": "TastyJollof2026!",
    },
    follow=True,
)
check("signup succeeds", response.status_code == 200)
user = User.objects.filter(username="smoketester").first()
check("user created", user is not None)
check("profile auto-created", hasattr(user, "profile"))
check("logged in after signup", response.context["user"].is_authenticated)
check("cart survived signup", len(client.get("/cart/").context["cart"]) == 3)

response = client.post(
    "/accounts/profile/",
    {
        "first_name": "Smoke",
        "last_name": "Tester",
        "email": "smoke@example.com",
        "full_name": "Smoke Tester",
        "phone_number": "08012345678",
        "delivery_address": "12 Admiralty Way, Lekki Phase 1, Lagos",
    },
    follow=True,
)
check("profile saves", response.status_code == 200)
user.refresh_from_db()
check("address persisted",
      user.profile.delivery_address.startswith("12 Admiralty Way"),
      user.profile.delivery_address)
check("profile is_complete", user.profile.is_complete)

# --- Checkout ---------------------------------------------------------------
print("\n== Checkout ==")
response = client.get("/orders/checkout/")
check("GET checkout", response.status_code == 200)
form = response.context["form"]
check("form prefills name", form["full_name"].value() == "Smoke Tester",
      str(form["full_name"].value()))
check("form prefills address",
      str(form["delivery_address"].value()).startswith("12 Admiralty Way"))

order_count_before = Order.objects.count()
response = client.post(
    "/orders/checkout/",
    {
        "full_name": "Smoke Tester",
        "email": "smoke@example.com",
        "phone_number": "08012345678",
        "delivery_address": "12 Admiralty Way, Lekki Phase 1, Lagos",
        "note": "Ring the bell twice",
        "payment_method": "pod",
    },
    follow=True,
)
check("POST checkout", response.status_code == 200)
check("order created", Order.objects.count() == order_count_before + 1)

order = Order.objects.filter(user=user).first()
check("order has reference", order and order.reference.startswith("SFE-"),
      order.reference if order else "no order")
check("order line items", order.items.count() == 1)
check("order quantity", order.items.first().quantity == 3)
check("order subtotal", order.subtotal == expected_subtotal,
      f"{order.subtotal} != {expected_subtotal}")
check("order total", order.total_price == order.subtotal + order.delivery_fee)
check("price snapshot", order.items.first().price == item.price)
check("cart cleared after order", len(client.get("/cart/").context["cart"]) == 0)
check("landed on success page", "orders/success" in response.request["PATH_INFO"]
      or response.request["PATH_INFO"].startswith("/orders/success"),
      response.request["PATH_INFO"])

# --- Order history ----------------------------------------------------------
print("\n== Orders ==")
check("GET order list", client.get("/orders/").status_code == 200)
check("GET order detail",
      client.get(f"/orders/{order.reference}/").status_code == 200)
check("GET order success",
      client.get(f"/orders/success/{order.reference}/").status_code == 200)

# Another user must not be able to read this order.
User.objects.filter(username="nosyneighbour").delete()
other = User.objects.create_user("nosyneighbour", password="TastyJollof2026!")
other_client = Client()
other_client.force_login(other)
check("order is owner-scoped",
      other_client.get(f"/orders/{order.reference}/").status_code == 404)

# --- Empty-cart checkout guard ---------------------------------------------
check("empty cart bounces from checkout",
      client.get("/orders/checkout/").status_code == 302)

# --- Catering + contact forms ----------------------------------------------
print("\n== Enquiry forms ==")
guest = Client()  # anonymous: these forms must work without an account

# A date well in the future so the clean_event_date check never trips on it.
future_date = (date.today() + timedelta(days=45)).isoformat()
catering_before = CateringRequest.objects.count()
response = guest.post(
    "/catering/",
    {
        "full_name": "Smoke Tester",
        "email": "smoke@example.com",
        "phone_number": "08012345678",
        "event_type": "wedding",
        "guest_count": 150,
        "event_date": future_date,
        "venue_area": "Ikeja, Lagos",
        "menu_ideas": "Jollof, small chops, suya",
    },
    follow=True,
)
check("POST catering (valid)", response.status_code == 200)
check("catering request saved",
      CateringRequest.objects.count() == catering_before + 1)
check("catering redirects after POST", response.redirect_chain != [],
      "no redirect — a refresh would resubmit")

# Below the 50-guest minimum and a date in the past: two field errors expected.
response = guest.post(
    "/catering/",
    {
        "full_name": "Smoke Tester",
        "email": "not-an-email",
        "phone_number": "123",
        "event_type": "wedding",
        "guest_count": 4,
        "event_date": (date.today() - timedelta(days=5)).isoformat(),
    },
)
check("invalid catering re-renders", response.status_code == 200)
form = response.context["form"]
check("guest_count error", "guest_count" in form.errors, str(form.errors))
check("event_date error", "event_date" in form.errors, str(form.errors))
check("email error", "email" in form.errors, str(form.errors))
check("phone_number error", "phone_number" in form.errors, str(form.errors))
check("errors rendered in HTML", "errorlist" in response.content.decode())
check("nothing saved on invalid catering",
      CateringRequest.objects.count() == catering_before + 1)

contact_before = ContactMessage.objects.count()
response = guest.post(
    "/contact/",
    {
        "full_name": "Smoke Tester",
        "email": "smoke@example.com",
        "phone_number": "",  # optional
        # subject is a choice field, not free text — send the stored value.
        "subject": ContactMessage.Subject.GENERAL,
        "message": "Do you deliver to Yaba on Sundays?",
    },
    follow=True,
)
check("POST contact (valid)", response.status_code == 200)
check("contact message saved", ContactMessage.objects.count() == contact_before + 1)

# Too-short message trips clean_message. Everything else stays valid so the
# failure is isolated to that one field.
response = guest.post(
    "/contact/",
    {
        "full_name": "Smoke Tester",
        "email": "smoke@example.com",
        "subject": ContactMessage.Subject.GENERAL,
        "message": "yo",
    },
)
check("invalid contact re-renders", response.status_code == 200)
check("message error", "message" in response.context["form"].errors,
      str(response.context["form"].errors))
check("nothing saved on invalid contact",
      ContactMessage.objects.count() == contact_before + 1)

# --- Cleanup ---------------------------------------------------------------
order.items.all().delete()
order.delete()
User.objects.filter(username__in=["smoketester", "nosyneighbour"]).delete()
CateringRequest.objects.filter(email="smoke@example.com").delete()
ContactMessage.objects.filter(email="smoke@example.com").delete()

print("\n" + "=" * 50)
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {', '.join(FAILURES)}")
else:
    print("All smoke tests passed.")
