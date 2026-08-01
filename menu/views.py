"""Customer-facing shop views: homepage, menu grid and item detail."""

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Category, FoodItem

# Sort keys accepted on ?sort=. Values are order_by() arguments; the trailing
# "name" keeps paging stable when the primary key ties.
SORT_OPTIONS = {
    "pop": ("-is_featured", "category__display_order", "name"),
    "lo": ("price", "name"),
    "hi": ("-price", "name"),
    "az": ("name",),
}
SORT_LABELS = [
    ("pop", "Popular"),
    ("lo", "Price: low to high"),
    ("hi", "Price: high to low"),
    ("az", "A–Z"),
]
DEFAULT_SORT = "pop"


def home(request):
    """Landing page: hero, category chips and a featured highlights row."""
    featured = (
        FoodItem.objects.available()
        .select_related("category")
        .filter(is_featured=True)[:6]
    )
    # If nothing is flagged featured yet, fall back to the newest items so the
    # homepage never looks empty on a fresh install.
    if not featured:
        featured = (
            FoodItem.objects.available()
            .select_related("category")
            .order_by("-created_at")[:6]
        )

    context = {
        "featured_items": featured,
        "categories": Category.objects.filter(is_active=True),
        "category_tiles": _category_tiles(),
    }
    return render(request, "menu/home.html", context)


def _category_tiles():
    """Pair each active category with a dish to use as its tile artwork.

    The homepage design leads with image-backed category tiles, but Category
    itself holds no image — so borrow one from a dish in that category,
    preferring a featured dish. Categories with no usable image still render;
    the template falls back to a flat colour tile.
    """
    tiles = []
    for category in Category.objects.filter(is_active=True):
        representative = (
            FoodItem.objects.available()
            .filter(category=category)
            .exclude(image="")
            .order_by("-is_featured", "name")
            .first()
        )
        tiles.append({"category": category, "item": representative})
    return tiles


def menu(request):
    """Shop grid with category filter, search, sort and pagination."""
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "").strip()

    items = FoodItem.objects.available().select_related("category")

    active_category = None
    if category_slug:
        active_category = Category.objects.filter(
            slug=category_slug, is_active=True
        ).first()
        if active_category:
            items = items.filter(category=active_category)

    if query:
        items = items.search(query)

    # An unknown or missing ?sort= falls back to "popular" rather than 400ing —
    # the value comes straight from a query string, so treat it as untrusted.
    items = items.order_by(*SORT_OPTIONS.get(sort, SORT_OPTIONS[DEFAULT_SORT]))

    paginator = Paginator(items, settings.MENU_PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page,
        "items": page.object_list,
        "categories": Category.objects.filter(is_active=True),
        "active_category": active_category,
        "query": query,
        "sort": sort if sort in SORT_OPTIONS else DEFAULT_SORT,
        "sort_choices": SORT_LABELS,
        "total_count": paginator.count,
    }
    return render(request, "menu/menu.html", context)


def food_detail(request, slug):
    """Single dish page with a few related items from the same category."""
    item = get_object_or_404(FoodItem.objects.select_related("category"), slug=slug)
    related = (
        FoodItem.objects.available()
        .filter(category=item.category)
        .exclude(pk=item.pk)[:4]
    )
    return render(
        request, "menu/food_detail.html", {"item": item, "related_items": related}
    )
