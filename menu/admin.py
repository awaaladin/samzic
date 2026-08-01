from django.contrib import admin
from django.utils.html import format_html

from .models import Category, FoodItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "display_order", "item_count", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.food_items.count()


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ["thumbnail", "name", "category", "price", "available", "is_featured"]
    list_display_links = ["thumbnail", "name"]
    list_editable = ["price", "available", "is_featured"]
    list_filter = ["available", "is_featured", "category"]
    search_fields = ["name", "description"]
    list_select_related = ["category"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at", "preview"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "category", "description"]}),
        ("Pricing & availability", {"fields": ["price", "available", "is_featured"]}),
        ("Image", {"fields": ["image", "preview"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]
    actions = ["mark_available", "mark_unavailable"]

    @admin.display(description="")
    def thumbnail(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="height:38px;width:38px;object-fit:cover;border-radius:6px;">',
            obj.image.url,
        )

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj.image:
            return "No image uploaded yet."
        return format_html(
            '<img src="{}" style="max-height:220px;border-radius:10px;">', obj.image.url
        )

    @admin.action(description="Mark selected items as available")
    def mark_available(self, request, queryset):
        updated = queryset.update(available=True)
        self.message_user(request, f"{updated} item(s) marked available.")

    @admin.action(description="Mark selected items as sold out")
    def mark_unavailable(self, request, queryset):
        updated = queryset.update(available=False)
        self.message_user(request, f"{updated} item(s) marked sold out.")
