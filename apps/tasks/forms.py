from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin
from apps.core.models import MEMBER_COLORS, Visibility

from .models import Task, TaskLabel

User = get_user_model()


class MemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name or obj.email


class TaskForm(StyledFormMixin, forms.ModelForm):
    assignee = MemberChoiceField(
        label=_("Responsable"), queryset=User.objects.none(), required=False, empty_label=_("Nadie")
    )
    labels = forms.ModelMultipleChoiceField(
        label=_("Etiquetas"),
        queryset=TaskLabel.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "visibility",
            "assignee",
            "due_date",
            "priority",
            "status",
            "description",
            "labels",
        ]
        widgets = {
            "visibility": forms.RadioSelect,
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"visibility": _("¿Para quién es?")}

    def __init__(self, *args, household, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["assignee"].queryset = User.objects.filter(
            memberships__household=household
        ).order_by("name")
        self.fields["labels"].queryset = TaskLabel.objects.visible_to(user, household)
        self.fields["labels"].widget.attrs["class"] = "size-4 accent-accent"
        self.fields["visibility"].choices = [
            (Visibility.SHARED, _("Del hogar: la ve todo el mundo")),
            (Visibility.PRIVATE, _("Personal: solo la ves tú")),
        ]
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        if self.instance.pk:
            del self.fields["visibility"]
            del self.fields["status"]  # el estado se cambia desde el tablero o el detalle

    def clean(self):
        data = super().clean()
        visibility = data.get("visibility") or (
            self.instance.visibility if self.instance.pk else None
        )
        owner_id = self.instance.owner_id if self.instance.pk else self.user.pk
        assignee = data.get("assignee")
        if visibility == Visibility.PRIVATE and assignee and assignee.pk != owner_id:
            self.add_error("assignee", _("Una tarea personal solo puede asignarse a ti."))
        return data

    def task_data(self) -> dict:
        data = {f: self.cleaned_data[f] for f in self._meta.fields if f in self.cleaned_data}
        data.pop("labels", None)
        return data


class QuickTaskForm(forms.Form):
    title = forms.CharField(max_length=200)


class LabelForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label=_("Nombre"), max_length=40)
    color = forms.ChoiceField(label=_("Color"), choices=[(c, c) for c in MEMBER_COLORS])


class CommentForm(forms.Form):
    body = forms.CharField(max_length=2000)


class SubtaskForm(forms.Form):
    title = forms.CharField(max_length=200)
