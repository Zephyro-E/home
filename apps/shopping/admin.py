from django.contrib import admin

from .models import GroceryItem, WishComment, WishItem, WishVote


@admin.register(GroceryItem)
class GroceryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "quantity", "is_checked", "household", "owner"]
    list_filter = ["is_checked", "household"]


class WishVoteInline(admin.TabularInline):
    model = WishVote
    extra = 0


class WishCommentInline(admin.TabularInline):
    model = WishComment
    extra = 0


@admin.register(WishItem)
class WishItemAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "visibility", "priority", "household", "owner"]
    list_filter = ["status", "visibility", "household"]
    inlines = [WishVoteInline, WishCommentInline]
