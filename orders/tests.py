from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cart.models import Cart, CartItem
from menu.models import Category, FoodItem

from .models import Order, OrderItem, OrderMessage


def _complete_profile(user):
    profile = user.profile
    profile.full_name = "Ada Obi"
    profile.phone_number = "+234 803 000 0000"
    profile.address_line = "12 Palm Avenue"
    profile.area = "Lekki Phase 1"
    profile.city = "Lagos"
    profile.state = "Lagos"
    profile.landmark = "Opposite the pharmacy"
    profile.save()
    return profile


class CheckoutProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ada", "ada@example.com", "pw-12345-xyz")
        self.food = FoodItem.objects.create(
            name="Jollof",
            price=Decimal("2500"),
            category=Category.objects.create(name="Rice"),
        )
        CartItem.objects.create(cart=Cart.objects.create(user=self.user), item=self.food, quantity=1)
        self.client.force_login(self.user)

    def test_incomplete_profile_is_sent_to_account_page_first(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:profile')}?next={reverse('orders:checkout')}",
        )

    def test_legacy_free_text_address_alone_is_not_complete(self):
        """A profile with only the old one-line address still has to give a city and state."""
        profile = self.user.profile
        profile.full_name, profile.phone_number = "Ada Obi", "08030000000"
        profile.address_line = "12 Palm Avenue"  # what the migration copies the old text into
        profile.save()
        self.assertFalse(profile.is_complete)

    def test_complete_profile_prefills_every_address_part(self):
        _complete_profile(self.user)
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        for text in ("12 Palm Avenue", "Lekki Phase 1", "Opposite the pharmacy"):
            self.assertContains(response, text)

    def test_address_is_composed_into_one_line(self):
        profile = _complete_profile(self.user)
        self.assertEqual(
            profile.delivery_address,
            "12 Palm Avenue, Lekki Phase 1, Lagos, Lagos (Near Opposite the pharmacy)",
        )

    def test_order_keeps_the_address_in_parts(self):
        _complete_profile(self.user)
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "full_name": "Ada Obi",
                "phone_number": "+234 803 000 0000",
                "email": "ada@example.com",
                "address_line": "12 Palm Avenue",
                "area": "Lekki Phase 1",
                "city": "Lagos",
                "state": "Lagos",
                "landmark": "Opposite the pharmacy",
                "payment_method": "pod",
            },
        )
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:success", args=[order.reference]))
        self.assertEqual((order.address_line, order.area, order.city, order.state), ("12 Palm Avenue", "Lekki Phase 1", "Lagos", "Lagos"))
        self.assertTrue(order.delivery_address.startswith("12 Palm Avenue, Lekki Phase 1"))

    def test_city_and_state_are_required_at_checkout(self):
        _complete_profile(self.user)
        response = self.client.post(
            reverse("orders:checkout"),
            {"full_name": "Ada", "phone_number": "08030000000", "address_line": "12 Palm Avenue"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_order_still_placed_when_the_payment_radio_is_missing(self):
        """The one payment method is the fallback, so an unclicked radio never blocks an order."""
        _complete_profile(self.user)
        self.client.post(
            reverse("orders:checkout"),
            {
                "full_name": "Ada Obi", "phone_number": "08030000000", "address_line": "12 Palm Avenue",
                "city": "Lagos", "state": "Lagos",
            },
        )
        order = Order.objects.get()
        self.assertEqual(order.payment_method, Order.PaymentMethod.PAY_ON_DELIVERY)


class OrderMessageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user("cust", "c@example.com", "pw-12345-xyz")
        self.other = User.objects.create_user("other", "o@example.com", "pw-12345-xyz")
        self.staff = User.objects.create_user("chef", "chef@example.com", "pw-12345-xyz", is_staff=True)
        self.order = self._order(self.customer)

    def _order(self, user, status=Order.Status.PENDING):
        order = Order.objects.create(
            user=user, full_name="Cust", phone_number="08030000000",
            address_line="1 Road", city="Lagos", state="Lagos",
            subtotal=Decimal("1000"), total_price=Decimal("1000"), status=status,
        )
        OrderItem.objects.create(order=order, name="Dish", price=Decimal("1000"), quantity=1)
        return order

    def test_customer_can_message_the_kitchen(self):
        self.client.force_login(self.customer)
        self.client.post(reverse("orders:message", args=[self.order.reference]), {"body": "No pepper"})
        message = OrderMessage.objects.get()
        self.assertEqual((message.sender, message.author, message.is_read), ("customer", self.customer, False))

    def test_kitchen_reply_is_seen_by_the_customer_and_marked_read(self):
        OrderMessage.objects.create(order=self.order, sender="kitchen", author=self.staff, body="Noted")
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(reverse("orders:list")), "NEW REPL")
        self.assertContains(self.client.get(reverse("orders:detail", args=[self.order.reference])), "Noted")
        self.assertFalse(OrderMessage.objects.filter(is_read=False).exists())

    def test_staff_reply_and_unread_flow(self):
        OrderMessage.objects.create(order=self.order, sender="customer", author=self.customer, body="Gate code 4471")
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse("console:kitchen")), self.order.reference)
        self.client.get(reverse("console:order_detail", args=[self.order.reference]))
        self.assertFalse(OrderMessage.objects.filter(sender="customer", is_read=False).exists())
        self.client.post(reverse("console:order_reply", args=[self.order.reference]), {"body": "Thanks"})
        self.assertEqual(OrderMessage.objects.filter(sender="kitchen").count(), 1)

    def test_closed_orders_take_no_new_messages(self):
        closed = self._order(self.customer, status=Order.Status.DELIVERED)
        self.client.force_login(self.customer)
        self.client.post(reverse("orders:message", args=[closed.reference]), {"body": "hello?"})
        self.assertFalse(OrderMessage.objects.filter(order=closed).exists())

    def test_cannot_message_someone_elses_order(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("orders:message", args=[self.order.reference]), {"body": "hi"})
        self.assertEqual(response.status_code, 404)

    def test_customers_cannot_use_the_console_reply(self):
        self.client.force_login(self.customer)
        response = self.client.post(reverse("console:order_reply", args=[self.order.reference]), {"body": "x"})
        self.assertEqual(response.status_code, 403)

    def test_blank_and_oversized_messages_are_rejected(self):
        self.client.force_login(self.customer)
        url = reverse("orders:message", args=[self.order.reference])
        self.client.post(url, {"body": "   "})
        self.client.post(url, {"body": "x" * (OrderMessage.MAX_LENGTH + 1)})
        self.assertFalse(OrderMessage.objects.exists())
