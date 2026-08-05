"""Menu catalogue: categories and the food items sold."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    """A grouping such as Rice, Soups or Drinks."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    # Lower numbers surface first in the filter chips; ties fall back to name.
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('menu:menu')}?category={self.slug}"


class FoodItemQuerySet(models.QuerySet):
    def available(self):
        """Only sellable items — used by every customer-facing view."""
        return self.filter(available=True, category__is_active=True)

    def search(self, term):
        if not term:
            return self
        return self.filter(
            models.Q(name__icontains=term)
            | models.Q(description__icontains=term)
            | models.Q(category__name__icontains=term)
        )


class FoodItem(models.Model):
    # Stock photos for dishes with no upload yet, matched against the category
    # name. First match wins, so keep the more specific keywords earlier.
    FALLBACK_IMAGES = (
        (("rice",), "jollof.jpg"),
        (("soup", "swallow"), "egusi.jpg"),
        (("grill",), "suya.jpg"),
        (("chop", "side", "snack"), "smallchops.jpg"),
        (("drink", "beverage"), "peppersoup.jpg"),
    )

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Price in Naira.",
    )
    image = models.ImageField(upload_to="food_items/", blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # never orphan menu items by deleting a category
        related_name="food_items",
    )
    available = models.BooleanField(
        default=True,
        help_text="Uncheck to hide from the shop without deleting.",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured items appear in the homepage highlights row.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FoodItemQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "name"]
        indexes = [
            models.Index(fields=["available", "category"]),
            models.Index(fields=["slug"]),
        ]

    @property
    def image_url(self):
        """The uploaded image, or a category-appropriate stock photo.

        Uploads go to Cloudinary in production (see settings.STORAGES), so
        self.image.url is already an absolute CDN URL there and a /media/ path
        locally. The fallbacks go through staticfiles rather than a hardcoded
        "/static/..." string so they keep resolving if STATIC_URL ever moves to
        a CDN prefix.
        """
        if self.image:
            return self.image.url

        cat = (self.category.name if self.category else "").lower()
        for keywords, filename in self.FALLBACK_IMAGES:
            if any(word in cat for word in keywords):
                return static(f"img/{filename}")
        return static("img/hero.jpg")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "item"
            slug, suffix = base, 2
            # Dish names repeat across categories, so de-duplicate the slug.
            while FoodItem.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("menu:food_detail", kwargs={"slug": self.slug})
