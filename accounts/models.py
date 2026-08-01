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
    delivery_address = models.TextField(
        blank=True,
        help_text="Street, area and any landmark that helps the rider find you.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username}"

    @property
    def display_name(self):
        """Best available name — used in the navbar and order confirmations."""
        return self.full_name or self.user.get_full_name() or self.user.username

    @property
    def is_complete(self):
        """Checkout needs all three fields, so nudge the user when any is blank."""
        return bool(self.full_name and self.phone_number and self.delivery_address)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """Guarantee every user (including superusers) has a profile row."""
    if created:
        Profile.objects.create(user=instance)
