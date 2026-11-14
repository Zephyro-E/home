from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils.translation import gettext_lazy as _

from . import services
from .models import Household

User = get_user_model()

INPUT_CSS = (
    "block w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-fg "
    "placeholder:text-muted/70 focus:border-accent focus:outline-none focus:ring-2 "
    "focus:ring-accent/30"
)


class StyledFormMixin:
    """Aplica el estilo común a todos los campos (ver templates/partials/form_fields.html)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "size-5 rounded border-border accent-accent")
            else:
                widget.attrs.setdefault("class", INPUT_CSS)


def client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "") if request else ""


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(
        label=_("Correo electrónico"),
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    error_messages = {
        "invalid_login": _("Correo o contraseña incorrectos."),
        "inactive": _("Esta cuenta está desactivada."),
        "locked": _("Demasiados intentos fallidos. Espera unos minutos y vuelve a probar."),
    }

    def clean(self):
        ip = client_ip(self.request)
        email = self.data.get("username", "")
        if services.login_is_locked(ip, email):
            raise forms.ValidationError(self.error_messages["locked"], code="locked")
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            services.register_login_failure(ip, email)
            raise
        services.reset_login_failures(ip, email)
        return cleaned


class NewAccountForm(StyledFormMixin, forms.Form):
    """Datos para crear una cuenta (asistente inicial o invitación)."""

    name = forms.CharField(label=_("Tu nombre"), max_length=100)
    email = forms.EmailField(
        label=_("Correo electrónico"), widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password1 = forms.CharField(
        label=_("Contraseña"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Al menos 8 caracteres; evita contraseñas comunes o solo numéricas."),
    )
    password2 = forms.CharField(
        label=_("Repite la contraseña"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("Ya existe una cuenta con este correo. Inicia sesión para continuar.")
            )
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Las contraseñas no coinciden."))
        elif p1:
            candidate = User(email=cleaned.get("email", ""), name=cleaned.get("name", ""))
            try:
                password_validation.validate_password(p1, candidate)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned


class SetupForm(NewAccountForm):
    household_name = forms.CharField(
        label=_("Nombre del hogar"),
        max_length=80,
        initial=_("Casa"),
        help_text=_("Por ejemplo: «Casa» o «Piso de Madrid». Se puede cambiar después."),
    )

    field_order = ["household_name", "name", "email", "password1", "password2"]


class HouseholdForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Household
        fields = ["name"]


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "language", "theme"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Ya existe otra cuenta con este correo."))
        return email


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass
