from django import forms
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin
from apps.core.models import Visibility
from apps.core.money import cents_to_input, parse_euros

from .models import WishItem

# Solo enlaces web: evita esquemas como javascript: o ftp:.
WEB_URL = URLValidator(schemes=["http", "https"])


class GroceryForm(StyledFormMixin, forms.Form):
    name = forms.CharField(
        label=_("Producto"),
        max_length=120,
        widget=forms.TextInput(
            attrs={"placeholder": _("Añadir producto…"), "autocomplete": "off", "required": True}
        ),
    )
    quantity = forms.CharField(
        label=_("Cantidad"),
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Cantidad"), "autocomplete": "off"}),
    )


class WishForm(StyledFormMixin, forms.ModelForm):
    price = forms.CharField(
        label=_("Precio aproximado (€)"),
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0,00"}),
    )
    url = forms.URLField(
        label=_("Enlace a la tienda"),
        required=False,
        assume_scheme="https",
        validators=[WEB_URL],
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )
    image_url = forms.URLField(
        label=_("Enlace a una imagen"),
        required=False,
        assume_scheme="https",
        validators=[WEB_URL],
        help_text=_("Opcional. La dirección de una foto del producto."),
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )

    class Meta:
        model = WishItem
        fields = ["name", "visibility", "description", "priority", "url", "image_url"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "visibility": forms.RadioSelect,
        }
        labels = {"visibility": _("¿Para quién es?")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].choices = [
            (Visibility.SHARED, _("Propuesta común: la ve todo el hogar")),
            (Visibility.PRIVATE, _("Deseo personal: solo lo ves tú")),
        ]
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        if self.instance.pk:
            # La visibilidad no se edita aquí: un deseo personal se comparte con su botón.
            del self.fields["visibility"]
            self.initial["price"] = cents_to_input(self.instance.estimated_price_cents)

    def clean_price(self):
        text = self.cleaned_data.get("price", "").strip()
        if not text:
            return None
        cents = parse_euros(text)
        if cents is None:
            raise forms.ValidationError(_("Escribe un importe válido, por ejemplo 12,50."))
        if cents > 100_000_000:  # 1 millón de euros
            raise forms.ValidationError(_("El importe es demasiado alto."))
        return cents

    def wish_data(self) -> dict:
        data = {f: self.cleaned_data[f] for f in self._meta.fields if f in self.cleaned_data}
        data["estimated_price_cents"] = self.cleaned_data.get("price")
        return data


class CommentForm(forms.Form):
    body = forms.CharField(label=_("Comentario"), max_length=2000)
