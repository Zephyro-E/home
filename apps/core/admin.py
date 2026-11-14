from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "name", "is_active", "is_staff", "date_joined")
    search_fields = ("email", "name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Datos personales"), {"fields": ("name",)}),
        (_("Permisos"), {"fields": ("is_active", "is_staff", "is_superuser")}),
        (_("Fechas"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),
    )
    filter_horizontal = ()
    list_filter = ("is_active", "is_staff")
