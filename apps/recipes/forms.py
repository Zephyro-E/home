from django import forms
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin
from apps.core.images import MAX_UPLOAD_BYTES
from apps.core.models import Visibility

from .models import Recipe

WEB_URL = URLValidator(schemes=["http", "https"])
IMAGE_ACCEPT = "image/jpeg,image/png,image/webp"


class RecipeForm(StyledFormMixin, forms.ModelForm):
    ingredients_text = forms.CharField(
        label=_("Ingredientes"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": _(
                    "Uno por línea, por ejemplo:\n200 g de harina\n2 huevos\n1/2 cebolla\nsal"
                ),
            }
        ),
        help_text=_("Escribe la cantidad delante para poder ajustar las raciones."),
    )
    photo = forms.FileField(
        label=_("Foto"),
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": IMAGE_ACCEPT}),
        help_text=_(
            "JPG, PNG o WEBP, hasta 10 MB. Se le quitan los datos ocultos (como la ubicación)."
        ),
    )
    remove_photo = forms.BooleanField(label=_("Quitar la foto actual"), required=False)
    source_url = forms.URLField(
        label=_("Receta original (enlace)"),
        required=False,
        assume_scheme="https",
        validators=[WEB_URL],
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )

    class Meta:
        model = Recipe
        fields = [
            "title",
            "course",
            "visibility",
            "servings",
            "prep_minutes",
            "cook_minutes",
            "description",
            "instructions",
            "tags",
            "source_url",
        ]
        widgets = {
            "visibility": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 2}),
            "instructions": forms.Textarea(
                attrs={"rows": 8, "placeholder": _("Un paso por línea.")}
            ),
            "tags": forms.TextInput(attrs={"placeholder": _("rápida, vegetariana, horno…")}),
            "servings": forms.NumberInput(attrs={"min": 1, "max": 50}),
            "prep_minutes": forms.NumberInput(attrs={"min": 0, "max": 1440}),
            "cook_minutes": forms.NumberInput(attrs={"min": 0, "max": 1440}),
        }
        labels = {"visibility": _("¿Para quién es?")}
        help_texts = {"tags": _("Separadas por comas.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].choices = [
            (Visibility.SHARED, _("Del hogar: la ve todo el mundo")),
            (Visibility.PRIVATE, _("Personal: solo la ves tú")),
        ]
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        self.fields["photo"].widget.attrs["class"] = (
            "block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-surface-2 "
            "file:px-3 file:py-2 file:font-medium"
        )
        if self.instance.pk:
            del self.fields["visibility"]
        else:
            del self.fields["remove_photo"]

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(_("La imagen es demasiado grande (máximo 10 MB)."))
        return photo

    def recipe_data(self) -> dict:
        d = dict(self.cleaned_data)
        data = {f: d[f] for f in self._meta.fields if f in d}
        data["ingredients_text"] = d.get("ingredients_text", "")
        data["image"] = d.get("photo")
        if "remove_photo" in d:
            data["remove_image"] = d["remove_photo"]
        return data


class CommentForm(forms.Form):
    body = forms.CharField(max_length=2000)
