"""Forms for the console. Reuses accounts.forms.TailwindFormMixin so every
input matches the storefront's own look — same classes, same focus ring.
"""

from django import forms

from accounts.forms import TailwindFormMixin
from menu.models import Category, FoodItem
from orders.models import Order
from pages.models import CateringPackage, CateringRequest, ContactMessage


class CategoryForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "display_order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class FoodItemForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = FoodItem
        fields = [
            "name", "category", "price", "description", "image",
            "available", "is_featured",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class OrderStatusForm(TailwindFormMixin, forms.ModelForm):
    """Kitchen-facing status update — the customer-facing fields are read-only
    here; edit those (delivery address, phone) from the Django admin fallback.
    """

    class Meta:
        model = Order
        fields = ["status", "payment_status"]


class CateringStatusForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = CateringRequest
        fields = ["status"]


class ContactHandledForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["is_handled"]


class CateringPackageForm(TailwindFormMixin, forms.ModelForm):
    """The price cards on the public catering page."""

    class Meta:
        model = CateringPackage
        fields = ["name", "description", "price_per_plate", "minimum_guests", "display_order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        labels = {"price_per_plate": "Price per plate (\u20a6)"}
