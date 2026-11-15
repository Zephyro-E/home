from django.contrib import admin

from .models import Recipe, RecipeIngredient


class IngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "servings", "visibility", "household"]
    list_filter = ["course", "household"]
    inlines = [IngredientInline]
