from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "kind",
        "all_day",
        "start_date",
        "starts_at",
        "visibility",
        "household",
    ]
    list_filter = ["kind", "visibility", "household"]
