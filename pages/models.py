"""Models for the marketing pages.

The static reference design had the catering and contact forms simply pop a
toast and reset — nothing was stored. Persisting them means an enquiry can
actually be answered, and the admin becomes the shared inbox for the kitchen.
"""

from django.db import models


class TimeStampedModel(models.Model):
    """Shared created/updated stamps for the enquiry models below."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
