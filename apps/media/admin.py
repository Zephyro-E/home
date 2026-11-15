from django.contrib import admin

from .models import Title


@admin.register(Title)
class TitleAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "status", "visibility", "household"]
    list_filter = ["kind", "status", "household"]
