from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cart.models import Cart, CartItem
from menu.models import Category, FoodItem


class CheckoutProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ada", "ada@example.com", "pw-12345-xyz")
        food = FoodItem.objects.create(
            name="Jollof",
            price=Decimal("2500"),
            category=Category.objects.create(name="Rice"),
        )
        CartItem.objects.create(cart=Cart.objects.create(user=self.user), item=food, quantity=1)
        self.client.force_login(self.user)

    def test_incomplete_profile_is_sent_to_account_page_first(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:profile')}?next={reverse('orders:checkout')}",
        )

    def test_complete_profile_prefills_checkout(self):
        profile = self.user.profile
        profile.full_name = "Ada Obi"
        profile.phone_number = "+234 803 000 0000"
        profile.delivery_address = "12 Palm Avenue, Lekki, Lagos"
        profile.save()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "12 Palm Avenue, Lekki, Lagos")
