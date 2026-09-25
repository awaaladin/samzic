"""Customer profiles.

Django's built-in User covers username/email/password, so we only add the
delivery details the checkout page needs. Keeping this as a 1-1 Profile (rather
than swapping in a custom User model) means the project stays compatible with
everything that expects ``auth.User``.
"""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from .address import STATE_CHOICES, compose_address


class Profile(models.Model):
    """Delivery details attached to a user account."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=140, blank=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Include the country code, e.g. +234 803 000 0000.",
    )
    # The address in parts, so a rider gets a street, an area and a landmark rather
    # than one line that says "Lekki".
    address_line = models.CharField(
        "Street address",
        max_length=200,
        blank=True,
        help_text="House or flat number and street, e.g. 12 Admiralty Way.",
    )
    area = models.CharField(
        "Area / neighbourhood",
        max_length=100,
        blank=True,
        help_text="e.g. Lekki Phase 1, Yaba, Ikeja GRA.",
    )
    city = models.CharField("City / town", max_length=80, blank=True)
    state = models.CharField(max_length=40, blank=True, choices=STATE_CHOICES)
    landmark = models.CharField(
        "Nearest landmark or rider directions",
        max_length=150,
        blank=True,
        help_text="Optional, but it saves the rider a phone call: gate colour, a bus stop, a shop.",
    )
    # The parts joined into one line. Built in save(); kept as a real column so
    # older rows, exports and the admin keep working from a single string.
    delivery_address = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username}"

    @property
    def display_name(self):
        """Best available name — used in the navbar and order confirmations."""
        return self.full_name or self.user.get_full_name() or self.user.username

    def compose_address(self):
        return compose_address(self.address_line, self.area, self.city, self.state, self.landmark)

    def save(self, *args, **kwargs):
        composed = self.compose_address()
        # Keep the one-line text in step with the parts. A legacy row that only has
        # the old free-text address (no parts yet) keeps it untouched.
        if composed:
            self.delivery_address = composed
            if "update_fields" in kwargs and kwargs["update_fields"] is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "delivery_address"}
        super().save(*args, **kwargs)

    @property
    def is_complete(self):
        """Checkout needs a name, a phone and a deliverable address in parts.

        Street, city and state are required; area and landmark help the rider but
        are optional. Nudge the customer when any required piece is blank.
        """
        return bool(
            self.full_name
            and self.phone_number
            and self.address_line
            and self.city
            and self.state
        )


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """Guarantee every user (including superusers) has a profile row."""
    if created:
        Profile.objects.create(user=instance)
