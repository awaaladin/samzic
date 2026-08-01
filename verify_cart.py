"""Verify the cart-page fixes against a real rendered response.

Covers step 5 of the bug report: put an item in the bag, load /cart/, and assert
the description is the real product copy (no dev notes) and that the back-link
is the new SVG arrow rather than a raw glyph.
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

from menu.models import FoodItem  # noqa: E402

setup_test_environment()

client = Client()
item = FoodItem.objects.filter(name__icontains="jollof").first() or FoodItem.objects.first()
print(f"Using: {item.name}")

response = client.post(f"/cart/add/{item.pk}/", {"quantity": 2}, follow=True)
print(f"add to cart -> {response.status_code}")

response = client.get("/cart/")
html = response.content.decode()
print(f"GET /cart/ -> {response.status_code}  ({len(html)} bytes)\n")

checks = [
    ("no raw {# in output", "{#" not in html),
    ("no raw #} in output", "#}" not in html),
    ("no {% leaking", "{%" not in html),
    ("no 'Quantity changes are POSTs' note", "Quantity changes are POSTs" not in html),
    ("no 'nesting forms' note", "nesting forms" not in html),
    ("back-link text present", "Continue browsing the menu" in html),
    ("back-link uses an SVG", 'd="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"' in html),
    ("no raw left-arrow glyph", "←" not in html and "&larr;" not in html),
    ("item name shown", item.name in html),
    # The cart row shows the quantity as text between the -/+ buttons, which is
    # why the leaked comment looked like it was the product description: the
    # cart never renders descriptions at all.
    ("quantity 2 shown", ">2</span>" in html),
]

# The description does render on the food detail page, so check the real copy there.
detail = client.get(item.get_absolute_url()).content.decode()
checks += [
    ("detail page: no raw {#", "{#" not in detail),
    ("detail page: real description", item.description[:40] in detail),
]

failures = 0
for label, ok in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    failures += 0 if ok else 1

print(f"\n{'All cart checks passed.' if not failures else f'{failures} failure(s).'}")
