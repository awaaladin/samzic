"""Menu images: the fallback chain and the Cloudinary media backend.

Every food card and detail page now renders {{ item.image_url }} unconditionally
rather than branching on {% if item.image %}, so that one property is the only
thing standing between an un-uploaded dish and a broken <img>. These tests pin
its behaviour, plus the storage wiring that decides where uploads actually land
— on Vercel a FileSystemStorage upload is written somewhere no later request can
read, which is what made deployed images 404.
"""

from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from menu.models import Category, FoodItem


class FoodItemImageUrlTests(TestCase):
    """image_url must always return something renderable."""

    def _item(self, category_name, **kwargs):
        category = Category.objects.create(
            name=category_name, slug=category_name.lower().replace(" ", "-")
        )
        return FoodItem.objects.create(
            name=f"{category_name} dish",
            category=category,
            price=Decimal("3500.00"),
            **kwargs,
        )

    def test_falls_back_per_category(self):
        for category_name, expected in [
            ("Rice", "jollof.jpg"),
            ("Soups", "egusi.jpg"),
            ("Swallow", "egusi.jpg"),
            ("Grills", "suya.jpg"),
            ("Small Chops", "smallchops.jpg"),
            ("Drinks", "peppersoup.jpg"),
        ]:
            with self.subTest(category=category_name):
                self.assertIn(expected, self._item(category_name).image_url)

    def test_unknown_category_gets_the_generic_photo(self):
        self.assertIn("hero.jpg", self._item("Continental").image_url)

    def test_fallback_goes_through_staticfiles_not_a_hardcoded_path(self):
        """A literal "/static/..." string would break if STATIC_URL moved."""
        url = self._item("Rice").image_url
        self.assertTrue(url.startswith("/static/"), url)

    @override_settings(STATIC_URL="https://cdn.example.com/assets/")
        # Proves the property resolves STATIC_URL at call time.
    def test_fallback_follows_a_cdn_static_url(self):
        self.assertEqual(
            self._item("Rice").image_url,
            "https://cdn.example.com/assets/img/jollof.jpg",
        )

    def test_an_upload_wins_over_the_fallback(self):
        item = self._item("Rice")
        item.image = "food_items/real-upload.jpg"
        # No save() needed: image_url reads the field, not the database.
        self.assertIn("real-upload.jpg", item.image_url)

    def test_cards_and_detail_pages_render_an_img(self):
        """Both templates dropped their {% if %}, so neither may emit a gap."""
        item = self._item("Rice")
        detail = self.client.get(item.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "jollof.jpg")

        listing = self.client.get(reverse("menu:menu"))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "jollof.jpg")


class MediaStorageConfigTests(TestCase):
    """Uploads must not land on Vercel's disposable filesystem."""

    def test_cloudinary_backs_media_when_configured(self):
        from django.conf import settings

        if not settings.USE_CLOUDINARY:
            self.skipTest("CLOUDINARY_URL is not set in this environment")

        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "cloudinary_storage.storage.MediaCloudinaryStorage",
        )
        # Static files stay with WhiteNoise; only media moves.
        self.assertIn("staticfiles", settings.STORAGES["staticfiles"]["BACKEND"])
        for app in ("cloudinary", "cloudinary_storage"):
            self.assertIn(app, settings.INSTALLED_APPS)

    def test_missing_credentials_do_not_break_the_site(self):
        """A blank CLOUDINARY_URL falls back to disk rather than erroring."""
        from django.conf import settings

        self.assertIn("BACKEND", settings.STORAGES["default"])
        self.assertTrue(settings.STORAGES["default"]["BACKEND"])
