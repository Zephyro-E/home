from django.contrib import admin

from .models import Account, Category, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "visibility", "is_archived", "household"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "household"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "kind",
        "amount_cents",
        "account",
        "category",
        "visibility",
        "household",
    ]
    list_filter = ["kind", "visibility", "household"]
