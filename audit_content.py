"""One-off audit: look for developer comment markers leaking into menu content."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from menu.models import Category, FoodItem  # noqa: E402

MARKERS = ["{#", "#}", "<!--", "-->", "{%", "%}"]

problems = []
for item in FoodItem.objects.all():
    for field in ("name", "description"):
        value = getattr(item, field) or ""
        for marker in MARKERS:
            if marker in value:
                problems.append((item.pk, "FoodItem", field, marker, value[:80]))

for category in Category.objects.all():
    for field in ("name", "description"):
        value = getattr(category, field) or ""
        for marker in MARKERS:
            if marker in value:
                problems.append((category.pk, "Category", field, marker, value[:80]))

print(f"Scanned {FoodItem.objects.count()} food items, {Category.objects.count()} categories.")
if problems:
    print(f"\n{len(problems)} problem(s) found:")
    for pk, model, field, marker, preview in problems:
        print(f"  {model} #{pk}.{field} contains {marker!r}: {preview}")
else:
    print("No comment markers in any name or description field. Content is clean.")

jollof = FoodItem.objects.filter(name__icontains="jollof").first()
if jollof:
    print(f"\nParty Jollof description reads:\n  {jollof.description}")
