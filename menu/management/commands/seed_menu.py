"""Populate the database with a realistic demo menu.

Usage::

    python manage.py seed_menu           # add anything missing
    python manage.py seed_menu --flush   # wipe menu data first, then reseed

Items are matched by name, so re-running is safe: existing dishes are updated
rather than duplicated. Orders are never touched.

Images are not uploaded here. The nine photos that ship with the project already
live in ``media/food_items/``, so we only need to point each ``FoodItem.image``
at the existing path — no file copying, no duplicated bytes. Dishes without a
photo render the card placeholder until someone uploads one in the admin.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from menu.models import Category, FoodItem

# Subdirectory of MEDIA_ROOT holding the shipped photos, and the prefix stored
# in the ImageField.
IMAGE_DIR = "food_items"

CATEGORIES = [
    ("Rice", "Party jollof, fried rice and friends.", 1),
    ("Swallow", "Pounded yam, amala and eba with the soup of the day.", 2),
    ("Soups", "Rich, slow-cooked soups and peppery broths.", 3),
    ("Grills", "Suya, asun, peppered meats and grilled fish.", 4),
    ("Small Chops", "Snacks and finger food for sharing.", 5),
    ("Sides", "Moi moi, plantain and everything that rounds a plate off.", 6),
    ("Drinks", "Chilled soft drinks, juices and mocktails.", 7),
]

# (name, category, price, description, featured, image filename or "")
ITEMS = [
    # --- the nine dishes that have photos ------------------------------------
    ("Party Jollof Rice", "Rice", "4500.00",
     "Smoky party-style jollof cooked over firewood heat, served with fried "
     "plantain and a grilled chicken quarter.", True, "jollof.jpg"),
    ("Fried Rice & Chicken", "Rice", "5500.00",
     "Vegetable fried rice with liver, sweet corn and green beans, finished "
     "with a peppered chicken drumstick.", False, "friedrice.jpg"),
    ("Egusi Soup & Pounded Yam", "Swallow", "6000.00",
     "Melon seed soup simmered with assorted beef, stockfish and ugu, paired "
     "with hand-pounded yam.", True, "egusi.jpg"),
    ("Amala, Ewedu & Gbegiri", "Swallow", "5000.00",
     "Abula the proper way — soft amala, silky ewedu, bean gbegiri and buka "
     "stew with assorted meat.", False, "amala.jpg"),
    ("Catfish Pepper Soup", "Soups", "6500.00",
     "Fresh catfish in a clear, aromatic broth of uziza, scent leaf and "
     "calabash nutmeg.", False, "peppersoup.jpg"),
    ("Beef Suya Platter", "Grills", "4000.00",
     "Charcoal-grilled beef skewers dusted in house yaji, served with sliced "
     "onions and fresh tomato.", False, "suya.jpg"),
    ("Asun — Peppered Goat", "Grills", "7000.00",
     "Smoked goat meat tossed in scotch bonnet, onions and bell pepper. The "
     "plate that ends arguments.", True, "asun.jpg"),
    ("Small Chops Platter", "Small Chops", "5000.00",
     "Samosa, spring rolls, puff puff and peppered gizzard — the standard "
     "opener for every Samzic event.", True, "smallchops.jpg"),
    ("Moi Moi (2 Wraps)", "Sides", "2000.00",
     "Steamed bean pudding with egg and corned beef, wrapped and cooked the "
     "traditional way.", False, "moimoi.jpg"),

    # --- rest of the menu, awaiting photos -----------------------------------
    ("Coconut Rice", "Rice", "4800.00",
     "Fragrant rice simmered in fresh coconut milk with mixed peppers.", False, ""),
    ("Ofada Rice & Ayamase", "Rice", "5500.00",
     "Local ofada rice with the classic green pepper designer stew.", False, ""),
    ("White Rice & Stew", "Rice", "3000.00",
     "Steamed white rice with our slow-simmered tomato and pepper stew.", False, ""),

    ("Afang Soup & Eba", "Swallow", "5200.00",
     "Rich Efik afang with waterleaf, periwinkle and dried fish.", False, ""),
    ("Ogbono Soup & Pounded Yam", "Swallow", "5000.00",
     "Draw soup with ogbono seeds, goat meat and stockfish.", False, ""),

    ("Goat Pepper Soup", "Soups", "4500.00",
     "Peppery, aromatic broth with tender goat meat. Made for cold evenings.", False, ""),
    ("Efo Riro", "Soups", "4200.00",
     "Spinach stewed with locust beans, assorted meat and ponmo.", False, ""),
    ("Banga Soup", "Soups", "5000.00",
     "Delta-style palm nut soup with catfish, served with starch.", False, ""),

    ("Grilled Croaker Fish", "Grills", "7500.00",
     "Whole croaker grilled with our house marinade, served with sauce.", False, ""),
    ("Peppered Chicken", "Grills", "5500.00",
     "Fried chicken tossed in a fiery pepper sauce.", False, ""),

    ("Puff Puff (10 pieces)", "Small Chops", "1500.00",
     "Soft, golden fried dough balls dusted with sugar.", False, ""),
    ("Meat Pie", "Small Chops", "1200.00",
     "Flaky pastry filled with seasoned minced beef and potatoes.", False, ""),
    ("Chin Chin", "Small Chops", "1000.00",
     "Crunchy fried pastry bites. Sold by the pack.", False, ""),

    ("Fried Plantain (Dodo)", "Sides", "1500.00",
     "Sweet ripe plantain fried golden. The side nobody skips.", False, ""),
    ("Coleslaw", "Sides", "1200.00",
     "Crisp cabbage and carrot in a light creamy dressing.", False, ""),

    ("Chapman", "Drinks", "1800.00",
     "The classic Nigerian mocktail with cucumber and a dash of bitters.", True, ""),
    ("Zobo Drink", "Drinks", "1200.00",
     "Chilled hibiscus drink infused with ginger and pineapple.", False, ""),
    ("Bottled Water", "Drinks", "500.00",
     "50cl chilled table water.", False, ""),
    ("Soft Drink (Can)", "Drinks", "800.00",
     "Coke, Fanta or Sprite. Served cold.", False, ""),
]


class Command(BaseCommand):
    help = "Seed the menu with demo categories and food items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing menu data before seeding. Orders are preserved.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            # FoodItem first: Category uses PROTECT.
            deleted, _ = FoodItem.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} menu row(s)."))

        categories = {}
        for name, description, order in CATEGORIES:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description, "display_order": order},
            )
            categories[name] = category
            if created:
                self.stdout.write(f"  + category: {name}")

        created_count = updated_count = 0
        attached = missing = 0

        for name, category_name, price, description, featured, filename in ITEMS:
            defaults = {
                "category": categories[category_name],
                "price": Decimal(price),
                "description": description,
                "is_featured": featured,
                "available": True,
            }

            if filename:
                # Only claim the image if the file is really on disk, otherwise
                # the template would render a broken <img> instead of the
                # placeholder it falls back to for an empty field.
                if (settings.MEDIA_ROOT / IMAGE_DIR / filename).exists():
                    defaults["image"] = f"{IMAGE_DIR}/{filename}"
                    attached += 1
                else:
                    missing += 1

            _, created = FoodItem.objects.update_or_create(name=name, defaults=defaults)
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Menu ready: {created_count} item(s) created, "
                f"{updated_count} updated, across {len(categories)} categories."
            )
        )
        self.stdout.write(f"Photos attached: {attached}.")
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"{missing} photo(s) expected in media/{IMAGE_DIR}/ were not found."
                )
            )
        self.stdout.write(
            "Dishes without a photo show the card placeholder — upload one per "
            "item in the admin."
        )
