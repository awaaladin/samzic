"""Checkout form — delivery details plus payment choice."""

from django import forms

from accounts.forms import TailwindFormMixin

from .models import Order


class CheckoutForm(TailwindFormMixin, forms.ModelForm):
    """Prefilled from the customer's profile, but editable per order."""

    class Meta:
        model = Order
        fields = [
            "full_name",
            "email",
            "phone_number",
            "delivery_address",
            "note",
            "payment_method",
        ]
        widgets = {
            "delivery_address": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(
                attrs={"rows": 2, "placeholder": "e.g. Gate code, no pepper, call on arrival"}
            ),
            # Radios are built from Order.PaymentMethod, so adding Paystack to
            # that TextChoices is enough to make it appear here.
            "payment_method": forms.RadioSelect,
        }
        labels = {
            "full_name": "Full name",
            "phone_number": "Phone number",
            "delivery_address": "Delivery address",
            "note": "Delivery note (optional)",
            "payment_method": "Payment method",
        }

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].required = False
        self.fields["email"].required = False
        # RadioSelect should not inherit the text-input styling.
        self.fields["payment_method"].widget.attrs.pop("class", None)

        if profile is not None and not self.is_bound:
            self.fields["full_name"].initial = profile.full_name or profile.display_name
            self.fields["phone_number"].initial = profile.phone_number
            self.fields["delivery_address"].initial = profile.delivery_address
            self.fields["email"].initial = profile.user.email

    def clean_delivery_address(self):
        address = self.cleaned_data["delivery_address"].strip()
        if len(address) < 10:
            raise forms.ValidationError(
                "Please give a fuller address so the rider can find you."
            )
        return address

    def clean_phone_number(self):
        phone = self.cleaned_data["phone_number"].strip()
        digits = phone.lstrip("+").replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 10:
            raise forms.ValidationError("Enter a reachable phone number.")
        return phone
