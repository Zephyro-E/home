from django.contrib import admin

from .models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "status", "visibility", "household"]
    list_filter = ["category", "status", "household"]
