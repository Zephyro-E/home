from datetime import datetime, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import RecurrenceFieldsMixin, StyledFormMixin
from apps.core.models import Visibility

from .models import Event

User = get_user_model()

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class EventForm(RecurrenceFieldsMixin, StyledFormMixin, forms.Form):
    title = forms.CharField(label=_("Título"), max_length=200)
    kind = forms.ChoiceField(label=_("Tipo"), choices=Event.Kind.choices)
    visibility = forms.ChoiceField(
        label=_("¿Para quién es?"),
        choices=[
            (Visibility.SHARED, _("Del hogar: lo ve todo el mundo")),
            (Visibility.PRIVATE, _("Personal: solo lo ves tú")),
        ],
        widget=forms.RadioSelect,
        initial=Visibility.SHARED,
    )
    all_day = forms.BooleanField(label=_("Todo el día"), required=False)
    start_date = forms.DateField(label=_("Empieza"), widget=DATE)
    start_time = forms.TimeField(label=_("Hora de inicio"), required=False, widget=TIME)
    end_date = forms.DateField(label=_("Termina"), required=False, widget=DATE)
    end_time = forms.TimeField(label=_("Hora de fin"), required=False, widget=TIME)
    location = forms.CharField(label=_("Lugar"), max_length=200, required=False)
    description = forms.CharField(
        label=_("Descripción"), required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    participants = forms.ModelMultipleChoiceField(
        label=_("Participantes"),
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, household, user, event=None, **kwargs):
        self.user = user
        self.event = event
        if event is not None and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from(event)
        super().__init__(*args, **kwargs)
        self.fields["participants"].queryset = User.objects.filter(
            memberships__household=household
        ).order_by("name")
        self.fields["participants"].label_from_instance = lambda u: u.name or u.email
        self.fields["participants"].widget.attrs["class"] = "size-4 accent-accent"
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        # Al elegir "Cumpleaños": todo el día y cada año (ver event_form.html).
        self.fields["kind"].widget.attrs["@change"] = (
            "if ($event.target.value === 'birthday') { allDay = true; $dispatch('set-yearly') }"
        )
        self.add_recurrence_fields(event.recurrence_rule if event else "")
        if event is not None:
            del self.fields["visibility"]  # se cambia con "Compartir con el hogar"

    @staticmethod
    def initial_from(event: Event) -> dict:
        data = {
            "title": event.title,
            "kind": event.kind,
            "all_day": event.all_day,
            "location": event.location,
            "description": event.description,
            "participants": list(event.participants.all()),
        }
        if event.all_day:
            data.update(start_date=event.start_date, end_date=event.end_date)
        else:
            start, end = timezone.localtime(event.starts_at), timezone.localtime(event.ends_at)
            data.update(
                start_date=start.date(),
                start_time=start.time().replace(second=0, microsecond=0),
                end_date=end.date(),
                end_time=end.time().replace(second=0, microsecond=0),
            )
        return data

    def clean(self):
        data = super().clean()
        start_date = data.get("start_date")
        if not start_date:
            return data
        end_date = data.get("end_date") or start_date
        if data.get("all_day"):
            if end_date < start_date:
                self.add_error("end_date", _("El final no puede ser anterior al inicio."))
            data["end_date"] = end_date
        else:
            start_time = data.get("start_time")
            if start_time is None:
                self.add_error("start_time", _("Indica la hora o marca «Todo el día»."))
                return data
            tz = timezone.get_current_timezone()
            starts = datetime.combine(start_date, start_time, tzinfo=tz)
            end_time = data.get("end_time")
            if end_time:
                ends = datetime.combine(end_date, end_time, tzinfo=tz)
            else:  # sin hora de fin: una hora (el día final, si se indicó otro)
                ends = datetime.combine(end_date, start_time, tzinfo=tz) + timedelta(hours=1)
            if ends < starts:
                self.add_error("end_time", _("El final no puede ser anterior al inicio."))
            data["starts_at"], data["ends_at"] = starts, ends
        visibility = data.get("visibility") or (self.event.visibility if self.event else None)
        owner_id = self.event.owner_id if self.event else self.user.pk
        if visibility == Visibility.PRIVATE and any(
            p.pk != owner_id for p in data.get("participants") or []
        ):
            self.add_error("participants", _("En un evento personal solo puedes participar tú."))
        return data

    def event_data(self) -> dict:
        d = self.cleaned_data
        data = {
            "title": d["title"],
            "kind": d["kind"],
            "all_day": d["all_day"],
            "location": d["location"],
            "description": d["description"],
            "participants": list(d["participants"]),
            "recurrence_rule": self.recurrence_rule(),
        }
        if "visibility" in d:
            data["visibility"] = d["visibility"]
        if d["all_day"]:
            data.update(start_date=d["start_date"], end_date=d["end_date"])
        else:
            data.update(starts_at=d["starts_at"], ends_at=d["ends_at"])
        return data
