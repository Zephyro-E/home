from django import forms
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin
from apps.core.models import Visibility

from .models import Place

WEB_URL = URLValidator(schemes=["http", "https"])


class PlaceForm(StyledFormMixin, forms.ModelForm):
    url = forms.URLField(
        label=_("Enlace (web, reseñas…)"),
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
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )

    class Meta:
        model = Place
        fields = [
            "name",
            "category",
            "visibility",
            "location",
            "status",
            "visited_on",
            "description",
            "url",
            "image_url",
        ]
        widgets = {
            "visibility": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 3}),
            "visited_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "location": forms.TextInput(attrs={"placeholder": _("Calle, barrio o ciudad")}),
        }
        labels = {"visibility": _("¿Para quién es?")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].choices = [
            (Visibility.SHARED, _("Del hogar: lo ve todo el mundo")),
            (Visibility.PRIVATE, _("Personal: solo lo ves tú")),
        ]
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        if self.instance.pk:
            del self.fields["visibility"]


class CommentForm(forms.Form):
    body = forms.CharField(max_length=2000)
