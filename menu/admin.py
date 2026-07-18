from django.contrib import admin

from .models import Category, Dish


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_fr", "name_en", "position", "is_active")
    list_editable = ("position", "is_active")


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name_fr", "category", "price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name_fr", "name_en")
