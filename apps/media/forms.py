from django import forms
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin
from apps.core.models import Visibility

from .models import Title

WEB_URL = URLValidator(schemes=["http", "https"])


class TitleForm(StyledFormMixin, forms.ModelForm):
    url = forms.URLField(
        label=_("Enlace (ficha, tráiler…)"),
        required=False,
        assume_scheme="https",
        validators=[WEB_URL],
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )
    image_url = forms.URLField(
        label=_("Enlace a una imagen (cartel)"),
        required=False,
        assume_scheme="https",
        validators=[WEB_URL],
        widget=forms.URLInput(attrs={"placeholder": "https://…"}),
    )

    class Meta:
        model = Title
        fields = [
            "title",
            "kind",
            "visibility",
            "status",
            "platform",
            "year",
            "genre",
            "synopsis",
            "url",
            "image_url",
        ]
        widgets = {
            "visibility": forms.RadioSelect,
            "synopsis": forms.Textarea(attrs={"rows": 3}),
            "year": forms.NumberInput(attrs={"min": 1880, "max": 2100}),
            "platform": forms.TextInput(attrs={"placeholder": _("Netflix, cine, DVD…")}),
        }
        labels = {"visibility": _("¿Para quién es?")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].choices = [
            (Visibility.SHARED, _("Del hogar: la ve todo el mundo")),
            (Visibility.PRIVATE, _("Personal: solo la ves tú")),
        ]
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        if self.instance.pk:
            del self.fields["visibility"]

    def clean_year(self):
        year = self.cleaned_data.get("year")
        if year is not None and not 1880 <= year <= 2100:
            raise forms.ValidationError(_("Año no válido."))
        return year


class ProgressForm(forms.Form):
    season = forms.IntegerField(min_value=1, max_value=99)
    episode = forms.IntegerField(min_value=0, max_value=999)


class CommentForm(forms.Form):
    body = forms.CharField(max_length=2000)
