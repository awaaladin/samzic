import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from orders.models import Order
from pages.models import CateringPackage

from . import analytics


class ConsoleTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user("chef", "chef@example.com", "pw-12345-xyz", is_staff=True)
        cls.customer = User.objects.create_user("cust", "c@example.com", "pw-12345-xyz")

    def make_order(self, days_ago=0, total="3000", status=Order.Status.DELIVERED, paid=True, **extra):
        order = Order.objects.create(
            user=self.customer, full_name="Cust", phone_number="08030000000",
            address_line="1 Road", city="Lagos", state="Lagos",
            subtotal=Decimal(total) - Decimal("500"), delivery_fee=Decimal("500"), total_price=Decimal(total),
            status=status,
            payment_status=Order.PaymentStatus.PAID if paid else Order.PaymentStatus.UNPAID,
            **extra,
        )
        stamp = timezone.now() - datetime.timedelta(days=days_ago)
        Order.objects.filter(pk=order.pk).update(created_at=stamp, paid_at=stamp if paid else None)
        return order


class AccessTests(ConsoleTestBase):
    def test_anonymous_goes_to_the_staff_sign_in(self):
        response = self.client.get(reverse("console:dashboard"))
        self.assertRedirects(response, f"{reverse('admin:login')}?next=/console/", fetch_redirect_response=False)

    def test_customers_get_403(self):
        self.client.force_login(self.customer)
        for name in ("dashboard", "order_insights", "revenue", "kitchen", "packages"):
            self.assertEqual(self.client.get(reverse(f"console:{name}")).status_code, 403, name)


class AdminLoginRoutingTests(ConsoleTestBase):
    def test_bare_admin_login_lands_on_the_console(self):
        response = self.client.post(
            reverse("admin:login"),
            {"username": "chef", "password": "pw-12345-xyz", "next": reverse("console:dashboard")},
        )
        self.assertRedirects(response, reverse("console:dashboard"), fetch_redirect_response=False)

    def test_admin_index_bounce_does_not_beat_the_console(self):
        """/admin/ sends signed-out visitors to login?next=/admin/ — that must not win."""
        response = self.client.get(f"{reverse('admin:login')}?next={reverse('admin:index')}")
        self.assertRedirects(
            response, f"{reverse('admin:login')}?next={reverse('console:dashboard')}", fetch_redirect_response=False
        )
        response = self.client.post(
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
            {"username": "chef", "password": "pw-12345-xyz", "next": reverse("admin:index")},
        )
        self.assertRedirects(response, reverse("console:dashboard"), fetch_redirect_response=False)

    def test_deep_admin_urls_are_still_honoured(self):
        deep = reverse("admin:orders_order_changelist")
        self.client.force_login(self.staff)
        response = self.client.get(f"{reverse('admin:login')}?next={deep}")
        self.assertRedirects(response, deep, fetch_redirect_response=False)

    def test_signed_in_staff_visiting_login_goes_to_the_console(self):
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get(reverse("admin:login")), reverse("console:dashboard"), fetch_redirect_response=False)

    def test_external_next_is_never_followed(self):
        self.client.force_login(self.staff)
        response = self.client.get(f"{reverse('admin:login')}?next=https://evil.example/")
        self.assertRedirects(response, reverse("console:dashboard"), fetch_redirect_response=False)


class InsightTests(ConsoleTestBase):
    def setUp(self):
        self.client.force_login(self.staff)
        self.make_order(days_ago=0, total="3000")
        self.make_order(days_ago=2, total="4000")
        self.make_order(days_ago=2, total="5000", status=Order.Status.PENDING, paid=False)
        self.make_order(days_ago=400, total="9000")

    def test_every_range_period_chart_combination_renders(self):
        for path in ("console:order_insights", "console:revenue"):
            for rng in ("7d", "30d", "90d", "12m", "ytd", "all"):
                for period in ("day", "month", "year"):
                    for chart in ("bar", "line", "smooth", "doughnut", "numbers"):
                        response = self.client.get(reverse(path), {"range": rng, "period": period, "chart": chart})
                        self.assertEqual(response.status_code, 200, (path, rng, period, chart))

    def test_garbage_filters_fall_back_instead_of_erroring(self):
        response = self.client.get(reverse("console:revenue"), {"range": "zz", "period": "??", "chart": "pie3d", "view": "x", "start": "nope"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("console:order_insights"), {"range": "custom", "start": "bad", "end": "worse"})
        self.assertEqual(response.status_code, 200)

    def test_revenue_only_counts_paid_orders_as_collected(self):
        data = analytics.revenue_insights({"range": "30d"})
        self.assertEqual(data["kpis"]["collected"], Decimal("7000"))       # 3000 + 4000
        self.assertEqual(data["kpis"]["outstanding"], Decimal("5000"))     # the pending, unpaid one
        self.assertEqual(data["kpis"]["paid_orders"], 2)
        self.assertEqual(data["kpis"]["delivery"], Decimal("1000"))
        self.assertEqual(data["kpis"]["food"], Decimal("6000"))

    def test_cancelled_orders_are_not_outstanding(self):
        self.make_order(days_ago=1, total="2000", status=Order.Status.CANCELLED, paid=False)
        data = analytics.revenue_insights({"range": "30d"})
        self.assertEqual(data["kpis"]["outstanding"], Decimal("5000"))

    def test_range_excludes_old_orders(self):
        self.assertEqual(analytics.order_insights({"range": "30d"})["kpis"]["orders"], 3)
        self.assertEqual(analytics.order_insights({"range": "all"})["kpis"]["orders"], 4)

    def test_daily_series_has_a_bucket_per_day_with_zeros(self):
        data = analytics.order_insights({"range": "7d", "period": "day"})
        self.assertEqual(len(data["rows"]), 7)
        self.assertEqual(sum(r["orders"] for r in data["rows"]), 3)
        self.assertIn(0, [r["orders"] for r in data["rows"]])

    def test_a_multi_year_daily_view_is_grouped_by_month(self):
        data = analytics.order_insights({"range": "all", "period": "day"})
        self.assertEqual(data["period"], "month")
        self.assertTrue(data["period_note"])

    def test_yearly_grouping(self):
        data = analytics.order_insights({"range": "all", "period": "year"})
        self.assertGreaterEqual(len(data["rows"]), 2)

    def test_status_filter(self):
        data = analytics.order_insights({"range": "30d", "status": "pending"})
        self.assertEqual(data["kpis"]["orders"], 1)

    def test_period_change_is_reported_against_the_previous_window(self):
        data = analytics.order_insights({"range": "7d"})
        self.assertEqual(data["kpis"]["orders"], 3)
        self.assertIsNone(data["kpis"]["change"])  # nothing in the 7 days before

    def test_csv_export(self):
        response = self.client.get(reverse("console:revenue"), {"range": "30d", "export": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        body = response.content.decode("utf-8-sig")
        self.assertIn("Reference", body.splitlines()[0])
        self.assertEqual(len(body.strip().splitlines()) - 1, 2)  # header + the two paid orders


class CateringPackageTests(ConsoleTestBase):
    def test_public_page_reads_prices_from_the_database(self):
        page = self.client.get(reverse("pages:catering"))
        self.assertContains(page, "&#8358;6,500")  # seeded by the migration
        self.client.force_login(self.staff)
        self.client.post(
            reverse("console:package_add"),
            {"name": "Gala", "description": "Big nights", "price_per_plate": "12345", "minimum_guests": 100, "display_order": 1, "is_active": "on"},
        )
        self.client.logout()
        page = self.client.get(reverse("pages:catering"))
        self.assertContains(page, "Gala")
        self.assertContains(page, "&#8358;12,345")

    def test_editing_a_price_changes_the_public_page(self):
        package = CateringPackage.objects.get(name="Weddings")
        self.client.force_login(self.staff)
        self.client.post(
            reverse("console:package_edit", args=[package.pk]),
            {"name": "Weddings", "description": "d", "price_per_plate": "7000", "minimum_guests": 50, "display_order": 0, "is_active": "on"},
        )
        page = self.client.get(reverse("pages:catering"))
        self.assertContains(page, "&#8358;7,000")
        self.assertNotContains(page, "&#8358;6,500")

    def test_hidden_packages_are_not_shown(self):
        CateringPackage.objects.filter(name="Corporate").update(is_active=False)
        self.assertNotContains(self.client.get(reverse("pages:catering")), "Corporate</h2>")


class CachePolicyTests(ConsoleTestBase):
    def test_public_pages_must_revalidate(self):
        header = self.client.get(reverse("menu:menu"))["Cache-Control"]
        self.assertIn("no-cache", header)
        self.assertIn("private", header)

    def test_signed_in_and_transactional_pages_are_never_stored(self):
        self.client.force_login(self.staff)
        for url in (reverse("console:dashboard"), reverse("cart:detail"), reverse("orders:list"), reverse("accounts:profile")):
            self.assertIn("no-store", self.client.get(url)["Cache-Control"], url)

    def test_json_and_redirects_are_not_stored(self):
        self.assertIn("no-store", self.client.get(reverse("cart:count"))["Cache-Control"])
