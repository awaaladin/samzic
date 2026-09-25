"""Checkout form — delivery details plus payment choice."""

from django import forms

from accounts.forms import TailwindFormMixin

from .models import Order, OrderMessage


class CheckoutForm(TailwindFormMixin, forms.ModelForm):
    """Prefilled from the customer's profile, but editable per order."""

    class Meta:
        model = Order
        fields = [
            "full_name",
            "email",
            "phone_number",
            "address_line",
            "area",
            "city",
            "state",
            "landmark",
            "note",
            "payment_method",
        ]
        widgets = {
            "address_line": forms.TextInput(attrs={"placeholder": "e.g. 12 Admiralty Way", "autocomplete": "address-line1"}),
            "area": forms.TextInput(attrs={"placeholder": "e.g. Lekki Phase 1", "autocomplete": "address-line2"}),
            "city": forms.TextInput(attrs={"placeholder": "e.g. Lagos", "autocomplete": "address-level2"}),
            "landmark": forms.TextInput(attrs={"placeholder": "e.g. Opposite Shoprite, blue gate"}),
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
            "landmark": "Nearest landmark (optional)",
            "note": "Delivery note (optional)",
            "payment_method": "Payment method",
        }

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].required = False
        self.fields["email"].required = False
        self.fields["landmark"].required = False
        self.fields["area"].required = False
        for name in ("address_line", "city", "state"):
            self.fields[name].required = True
        self.fields["state"].choices = [("", "Select state")] + list(self.fields["state"].choices)[1:]
        # RadioSelect should not inherit the text-input styling. The input is
        # hidden and the card next to it (checkout.html) shows the selected state.
        self.fields["payment_method"].widget.attrs["class"] = "peer sr-only"
        # There is one payment method today. If the field ever arrives empty (a
        # form restored by the browser, a stripped POST) fall back to it rather
        # than blocking the order on a control the customer cannot see.
        default = Order.PaymentMethod.PAY_ON_DELIVERY.value
        self.fields["payment_method"].initial = default
        if self.is_bound and not self.data.get("payment_method"):
            self.data = self.data.copy()
            self.data["payment_method"] = default

        if profile is not None and not self.is_bound:
            self.fields["full_name"].initial = profile.full_name or profile.display_name
            self.fields["phone_number"].initial = profile.phone_number
            for name in ("address_line", "area", "city", "state", "landmark"):
                self.fields[name].initial = getattr(profile, name)
            self.fields["email"].initial = profile.user.email

    def clean_address_line(self):
        line = self.cleaned_data["address_line"].strip()
        if len(line) < 5:
            raise forms.ValidationError(
                "Please give a street address so the rider can find you."
            )
        return line

    def save(self, commit=True):
        # delivery_address is the parts joined into one line (Order.save builds it),
        # so it never comes from the form.
        order = super().save(commit=False)
        order.delivery_address = order.compose_address()
        if commit:
            order.save()
        return order

    def clean_phone_number(self):
        phone = self.cleaned_data["phone_number"].strip()
        digits = phone.lstrip("+").replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 10:
            raise forms.ValidationError("Enter a reachable phone number.")
        return phone


class OrderMessageForm(TailwindFormMixin, forms.Form):
    """A note to (or from) the kitchen about one order."""

    body = forms.CharField(
        label="Message",
        max_length=OrderMessage.MAX_LENGTH,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "maxlength": OrderMessage.MAX_LENGTH,
                "placeholder": "e.g. No pepper please · the gate code is 4471 · can you deliver after 6pm?",
            }
        ),
    )

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Write a message first.")
        return body
