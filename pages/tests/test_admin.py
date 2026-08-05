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

    def test_control_room_route_exists(self):
        response = self.client.get(reverse("control_room"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Control room")
        self.assertContains(response, "Open full Django admin")

    def test_non_staff_cannot_reach_control_room(self):
        self.client.logout()
        User.objects.create_user(username="customer", password="pw-for-tests-only")
        self.client.login(username="customer", password="pw-for-tests-only")
        response = self.client.get(reverse("control_room"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])


class BrandedAdminLoginTests(TestCase):
    """The staff gate is branded, but must stay Django's login underneath.

    The reported symptom was "the custom admin panel redirects me to the Django
    panel" — the control room was branded while the login in front of it was
    not. Overriding admin/login.html fixes the look; these tests assert the
    security behaviour it wraps is unchanged.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="kitchen", email="kitchen@samzic.com", password="pw-for-tests-only"
        )

    def test_login_page_is_branded(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff sign in")
        self.assertContains(response, "SAMZIC CONTROL ROOM")
        # Not Django's stock heading.
        self.assertNotContains(response, "Django administration")

    def test_login_redirects_back_to_the_requested_page(self):
        """?next= must survive the branded template, or login dead-ends."""
        response = self.client.post(
            reverse("admin:login"),
            {
                "username": "kitchen",
                "password": "pw-for-tests-only",
                "next": reverse("control_room"),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(reverse("control_room"), 302)])
        self.assertContains(response, "Control room")

    def test_bad_credentials_show_the_branded_error(self):
        response = self.client.post(
            reverse("admin:login"), {"username": "kitchen", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sz-alert")
        self.assertContains(response, "staff account")

    def test_non_staff_still_rejected_by_the_branded_form(self):
        User.objects.create_user(username="customer", password="pw-for-tests-only")
        response = self.client.post(
            reverse("admin:login"),
            {"username": "customer", "password": "pw-for-tests-only"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sz-alert")
        self.assertNotIn("_auth_user_id", self.client.session)


class ChangeHistoryTests(TestCase):
    """Site-wide audit trail over django.contrib.admin's LogEntry."""

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

    def _log(self, action_flag, message):
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        return LogEntry.objects.create(
            user=self.admin,
            content_type=ContentType.objects.get_for_model(FoodItem),
            object_id=str(self.food.pk),
            object_repr=str(self.food),
            action_flag=action_flag,
            change_message=message,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_lists_recorded_changes(self):
        from django.contrib.admin.models import CHANGE

        self._log(CHANGE, "Changed price.")
        response = self.client.get(reverse("admin_change_history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change history")
        self.assertContains(response, "Changed price.")
        self.assertContains(response, "kitchen")

    def test_filters_by_action_and_search(self):
        from django.contrib.admin.models import ADDITION, CHANGE

        self._log(ADDITION, "Added the dish.")
        self._log(CHANGE, "Changed price.")

        changed_only = self.client.get(reverse("admin_change_history"), {"action": "2"})
        self.assertContains(changed_only, "Changed price.")
        self.assertNotContains(changed_only, "Added the dish.")

        searched = self.client.get(reverse("admin_change_history"), {"q": "price"})
        self.assertContains(searched, "Changed price.")
        self.assertNotContains(searched, "Added the dish.")

    def test_empty_state_when_nothing_logged(self):
        response = self.client.get(reverse("admin_change_history"))
        self.assertContains(response, "Nothing has been changed through the admin yet")

    def test_does_not_shadow_djangos_per_object_history(self):
        """A template at admin/history.html would break every object's history."""
        response = self.client.get(
            reverse("admin:menu_fooditem_history", args=[self.food.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_non_staff_cannot_read_the_audit_trail(self):
        self.client.logout()
        User.objects.create_user(username="customer", password="pw-for-tests-only")
        self.client.login(username="customer", password="pw-for-tests-only")
        response = self.client.get(reverse("admin_change_history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
