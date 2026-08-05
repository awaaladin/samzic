"""Account flows: signup, the profile dashboard, and admin seeding.

Two of these cover bugs that made the pages return 500 in production rather
than anything subtle — a missing {% load %} takes a whole page down, and the
template engine only finds out at render time, so a test that fetches the page
is the only thing that catches it.
"""

from decimal import Decimal
from io import StringIO
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse


class ProfileDashboardTests(TestCase):
    """The customer dashboard. Was returning 500: intcomma without humanize."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="tunde", email="tunde@example.com", password="pw-for-tests-only"
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_profile_renders_for_a_logged_in_customer(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My profile")
        self.assertContains(response, "Delivery details")

    def test_profile_renders_order_totals(self):
        """Exercises the intcomma filter that previously crashed the page."""
        from orders.models import Order

        Order.objects.create(
            user=self.user,
            full_name="Tunde A",
            phone_number="08030000000",
            delivery_address="1 Test Road",
            subtotal=Decimal("12500.00"),
            total_price=Decimal("12500.00"),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        # intcomma groups the thousands; without {% load humanize %} this 500s.
        self.assertContains(response, "12,500.00")

    def test_dashboard_and_account_aliases_reach_the_profile(self):
        self.client.force_login(self.user)
        for name in ("dashboard", "account_dashboard"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "My profile")


class SignUpPageTests(TestCase):
    def test_signup_page_renders(self):
        """Was returning 500: {% static %} used without {% load static %}."""
        response = self.client.get(reverse("accounts:signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your account")

    def test_signup_fits_one_screen_layout(self):
        """The fields sit in a two-column grid so the button stays above the fold."""
        response = self.client.get(reverse("accounts:signup"))
        self.assertContains(response, "sm:grid-cols-2")

    def test_password_rules_have_indicator_dots(self):
        """The JS marks .rule-dot; without the spans it throws on every keypress."""
        response = self.client.get(reverse("accounts:signup"))
        # Four rules, four dots. Matching the class attribute rather than the
        # bare name avoids counting the selector inside the inline script.
        self.assertContains(response, 'class="rule-dot', count=4)

    def test_signup_creates_the_account_and_profile_details(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "full_name": "Tunde Adeyemi",
                "phone_number": "08030000000",
                "email": "new@example.com",
                "username": "tundeeats",
                "password1": "kJ8-forkbeard-2x",
                "password2": "kJ8-forkbeard-2x",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="tundeeats")
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.profile.full_name, "Tunde Adeyemi")
        self.assertEqual(user.profile.phone_number, "08030000000")


class SeedSuperuserCommandTests(TestCase):
    """Deployments have no TTY, so the admin account comes from the environment."""

    def test_creates_the_superuser(self):
        out = StringIO()
        call_command(
            "seed_superuser", username="boss", password="pw-for-tests-only", stdout=out
        )
        user = User.objects.get(username="boss")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.check_password("pw-for-tests-only"))

    def test_email_is_taken_from_an_email_style_username(self):
        call_command(
            "seed_superuser", username="boss@samzic.com", password="pw-for-tests-only"
        )
        self.assertEqual(
            User.objects.get(username="boss@samzic.com").email, "boss@samzic.com"
        )

    def test_rerunning_promotes_rather_than_duplicating(self):
        User.objects.create_user(username="boss", password="pw-for-tests-only")
        call_command("seed_superuser", username="boss", password="ignored")
        self.assertEqual(User.objects.filter(username="boss").count(), 1)
        user = User.objects.get(username="boss")
        self.assertTrue(user.is_superuser)
        # Without --reset-password the existing password must survive.
        self.assertTrue(user.check_password("pw-for-tests-only"))

    def test_reset_password_flag_changes_the_password(self):
        User.objects.create_user(username="boss", password="old-password")
        call_command(
            "seed_superuser", username="boss", password="new-password", reset_password=True
        )
        self.assertTrue(User.objects.get(username="boss").check_password("new-password"))

    def test_missing_configuration_is_an_error_not_a_silent_skip(self):
        """No env vars, no arguments — fail loudly rather than skip silently.

        The variables have to be cleared from os.environ itself: the command
        reads them through environ.Env(), which goes straight to the process
        environment, and .env supplies them locally.
        """
        with patch.dict(os.environ, {"ADMIN_USERNAME": "", "ADMIN_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("seed_superuser", username="", password="")
