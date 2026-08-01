"""Forms for the catering quote request and the contact message."""

from datetime import date

from django import forms

from accounts.forms import TailwindFormMixin

from .models import CateringRequest, ContactMessage

# The catering page advertises this in the copy, so validate against it.
MINIMUM_GUESTS = 50


class CateringRequestForm(TailwindFormMixin, forms.ModelForm):
    """Quote request. Everything the kitchen needs to price an event."""

    class Meta:
        model = CateringRequest
        fields = [
            "full_name",
            "email",
            "phone_number",
            "event_type",
            "guest_count",
            "event_date",
            "venue_area",
            "menu_ideas",
        ]
        labels = {
            "full_name": "Name",
            "phone_number": "Phone",
            "guest_count": "Guests",
            "venue_area": "Venue area",
            "menu_ideas": "Menu ideas",
        }
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "guest_count": forms.NumberInput(
                attrs={"min": MINIMUM_GUESTS, "placeholder": "150"}
            ),
            "venue_area": forms.TextInput(attrs={"placeholder": "Ikeja, Lagos"}),
            "menu_ideas": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Jollof, small chops, grills…"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["venue_area"].required = False
        self.fields["menu_ideas"].required = False

    def clean_guest_count(self):
        guests = self.cleaned_data["guest_count"]
        if guests < MINIMUM_GUESTS:
            raise forms.ValidationError(
                f"We cater from {MINIMUM_GUESTS} guests upwards. "
                "For a smaller party, order from the menu instead."
            )
        return guests

    def clean_event_date(self):
        event_date = self.cleaned_data["event_date"]
        if event_date < date.today():
            raise forms.ValidationError("That date has already passed.")
        return event_date

    def clean_phone_number(self):
        phone = self.cleaned_data["phone_number"].strip()
        if sum(character.isdigit() for character in phone) < 10:
            raise forms.ValidationError("Enter a phone number we can call you on.")
        return phone


class ContactMessageForm(TailwindFormMixin, forms.ModelForm):
    """General enquiry form."""

    class Meta:
        model = ContactMessage
        fields = ["full_name", "email", "phone_number", "subject", "message"]
        labels = {"full_name": "Name", "phone_number": "Phone"}
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].required = False

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError(
                "Tell us a little more so we can answer properly."
            )
        return message
