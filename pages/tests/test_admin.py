"""The branded admin must keep every capability the default admin has.

The point of subclassing AdminSite rather than hand-rolling a panel is that
add/change/delete, permissions, inlines and bulk actions keep working. These
tests assert that, so a future template override cannot quietly break them.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from menu.models import Category, FoodItem


class AdminSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="kitchen", email="kitchen@samzic.com", password="pw-for-tests-only"
        )
        cls.category = Category.objects.create(name="Rice", slug="rice")
        cls.food = FoodItem.objects.create(
            name="Jollof Rice",
            slug="jollof-rice",
            category=cls.category,
            price=Decimal("3500.00"),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dashboard_renders_with_branding_and_stats(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samzic Foods Empire")
        self.assertContains(response, "Orders today")
        self.assertContains(response, "On the menu")

    def test_dashboard_keeps_django_app_list(self):
        """{{ block.super }} must still render the model list."""
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Food items")
        self.assertContains(response, "Orders")

    def test_can_add_food_item(self):
        response = self.client.post(
            reverse("admin:menu_fooditem_add"),
            {
                "name": "Fried Rice",
                "slug": "fried-rice",
                "category": self.category.pk,
                "description": "Party style.",
                "price": "4000.00",
                "available": "on",
                "_save": "Save",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(FoodItem.objects.filter(slug="fried-rice").exists())

    def test_can_delete_food_item(self):
        target = FoodItem.objects.create(
            name="Temp Dish", slug="temp-dish", category=self.category, price=Decimal("100.00")
        )
        response = self.client.post(
            reverse("admin:menu_fooditem_delete", args=[target.pk]),
            {"post": "yes"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FoodItem.objects.filter(pk=target.pk).exists())

    def test_bulk_action_still_works(self):
        self.client.post(
            reverse("admin:menu_fooditem_changelist"),
            {
                "action": "mark_unavailable",
                "_selected_action": [str(self.food.pk)],
            },
        )
        self.food.refresh_from_db()
        self.assertFalse(self.food.available)

    def test_user_admin_and_all_models_are_registered(self):
        """Every app's models must be reachable, including auth Users."""
        for url_name in [
            "admin:auth_user_changelist",
            "admin:menu_category_changelist",
            "admin:menu_fooditem_changelist",
            "admin:orders_order_changelist",
            "admin:pages_contactmessage_changelist",
            "admin:pages_cateringrequest_changelist",
        ]:
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_non_staff_cannot_reach_admin(self):
        self.client.logout()
        User.objects.create_user(username="customer", password="pw-for-tests-only")
        self.client.login(username="customer", password="pw-for-tests-only")
        response = self.client.get(reverse("admin:index"))
        # Django bounces non-staff to the admin login rather than serving it.
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_dashboard_survives_a_broken_stat(self):
        """each_context swallows stat errors so the admin never hard-fails."""
        from unittest.mock import patch

        with patch(
            "config.admin.SamzicAdminSite.dashboard_stats",
            side_effect=RuntimeError("table missing"),
        ):
            response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Food items")
