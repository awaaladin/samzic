"""Models for the marketing pages.

The static reference design had the catering and contact forms simply pop a
toast and reset — nothing was stored. Persisting them means an enquiry can
actually be answered, and the admin becomes the shared inbox for the kitchen.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class TimeStampedModel(models.Model):
    """Shared created/updated stamps for the enquiry models below."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CateringPackage(TimeStampedModel):
    """A catering price card shown on the catering page.

    The prices used to be typed into the template, so changing one meant a code
    change and a deploy. They live here now and are edited from the console (or
    the Django admin) like any other content.
    """

    name = models.CharField(max_length=80)
    description = models.CharField(max_length=220, blank=True)
    price_per_plate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Starting price per plate, in Naira.",
    )
    minimum_guests = models.PositiveIntegerField(
        default=50,
        help_text="Smallest event this price applies to.",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Lower numbers appear first."
    )
    is_active = models.BooleanField(
        default=True, help_text="Untick to hide from the catering page."
    )

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name} — ₦{self.price_per_plate:,.0f} / plate"


class CateringRequest(TimeStampedModel):
    """A quote request submitted from the catering page."""

    class EventType(models.TextChoices):
        WEDDING = "wedding", "Wedding"
        CORPORATE = "corporate", "Corporate"
        BIRTHDAY = "birthday", "Birthday"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        NEW = "new", "New"
        QUOTED = "quoted", "Quoted"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    event_type = models.CharField(
        max_length=20, choices=EventType.choices, default=EventType.WEDDING
    )
    # The reference page advertises a 50-guest minimum; the form enforces it.
    guest_count = models.PositiveIntegerField()
    event_date = models.DateField()
    venue_area = models.CharField(max_length=120, blank=True)
    menu_ideas = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "catering request"
        verbose_name_plural = "catering requests"

    def __str__(self):
        return f"{self.full_name} — {self.guest_count} guests on {self.event_date}"


class ContactMessage(TimeStampedModel):
    """A message submitted from the contact page."""

    class Subject(models.TextChoices):
        GENERAL = "general", "General enquiry"
        ORDER_ISSUE = "order_issue", "Order issue"
        CATERING = "catering", "Catering"
        PARTNERSHIP = "partnership", "Partnership"

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    subject = models.CharField(
        max_length=20, choices=Subject.choices, default=Subject.GENERAL
    )
    message = models.TextField()
    is_handled = models.BooleanField(
        default=False,
        help_text="Tick once someone has replied to this message.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.get_subject_display()}"
