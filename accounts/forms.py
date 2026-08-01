"""Forms for signup and profile editing.

Every form here adds Tailwind classes in ``__init__`` rather than in the
template, so the markup stays clean and the styling is defined in one place.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Profile

# One shared class string keeps every input looking identical.
# Matches the savory-serve design system: bone fill, hairline ink border,
# ember focus ring (the focus colour itself is set in base.html's <style>).
INPUT_CLASSES = (
    "w-full rounded-xl border border-ink/15 bg-bone px-4 py-3 text-sm text-ink "
    "placeholder-ink/35 transition focus:border-ember "
    "focus:ring-2 focus:ring-ember/15"
)


class TailwindFormMixin:
    """Apply the shared input styling to every visible widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {INPUT_CLASSES}".strip()


class SignUpForm(TailwindFormMixin, UserCreationForm):
    """Username + email + password, with email uniqueness enforced."""

    email = forms.EmailField(
        required=True,
        label="Email address",
        help_text="Your order confirmation and delivery updates go here.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Django ships help_text as raw HTML — password1 in particular is a
        # <ul> of validator messages. Rendering that inside the field partial
        # dumps a bulleted wall of text into the middle of the form. The rules
        # still apply; the template shows them as a designed checklist instead.
        self.fields["username"].help_text = "Letters, digits and @ . + - _ only."
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""

        self.fields["username"].label = "Username"
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"

        placeholders = {
            "username": "e.g. tundeeats",
            "email": "you@example.com",
            "password1": "At least 8 characters",
            "password2": "Type it once more",
        }
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder

        # Let the browser's password manager offer a strong password and stop
        # it autofilling the confirm box with a saved credential.
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["username"].widget.attrs["autofocus"] = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        # Django's User model does not enforce this, but a food shop needs it:
        # order lookups by email must be unambiguous.
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(TailwindFormMixin, AuthenticationForm):
    """Standard auth form, restyled."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "Your username", "autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"placeholder": "Your password", "autocomplete": "current-password"}
        )


class ProfileForm(TailwindFormMixin, forms.ModelForm):
    """Delivery details — also reused to prefill the checkout page."""

    class Meta:
        model = Profile
        fields = ["full_name", "phone_number", "delivery_address"]
        widgets = {
            "delivery_address": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "full_name": "Full name",
            "phone_number": "Phone number",
            "delivery_address": "Delivery address",
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if phone:
            digits = phone.lstrip("+").replace(" ", "").replace("-", "")
            if not digits.isdigit():
                raise forms.ValidationError(
                    "Enter a valid phone number using digits, spaces and an optional +."
                )
            if len(digits) < 10:
                raise forms.ValidationError("That phone number looks too short.")
        return phone


class UserDetailsForm(TailwindFormMixin, forms.ModelForm):
    """Lets the customer correct the email they signed up with."""

    class Meta:
        model = User
        fields = ["email"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email
