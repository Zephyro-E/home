"""Lógica del calendario: crear/editar eventos, expandir repeticiones y proyectar tareas.

Las tareas con fecha límite se muestran en el calendario al consultarlo, sin copiarse
como eventos (ADR-012): siguen siendo la misma tarea y enlazan a ella.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import recurrence
from apps.core.models import Membership, Visibility
from apps.tasks.models import Task

from .models import KIND_COLORS, KIND_DOTS, TASK_COLOR, TASK_DOT, Event

MAX_RANGE_DAYS = 400  # protección: nunca se expanden rangos enormes


def events_for(user, household):
    return Event.objects.visible_to(user, household).prefetch_related("participants")


# --- Crear, editar, borrar ----------------------------------------------------------------


def _check(household, owner, data):
    visibility = data.get("visibility", Visibility.SHARED)
    participants = list(data.get("participants") or [])
    member_ids = set(
        Membership.objects.filter(household=household).values_list("user_id", flat=True)
    )
    if any(p.pk not in member_ids for p in participants):
        raise ValidationError(_("Los participantes deben ser miembros del hogar."))
    if visibility == Visibility.PRIVATE and any(p.pk != owner.pk for p in participants):
        raise ValidationError(_("En un evento personal solo puedes participar tú."))
    if data.get("recurrence_rule") and not recurrence.is_valid(data["recurrence_rule"]):
        raise ValidationError(_("La repetición no es válida."))
    if data.get("all_day"):
        if data["end_date"] < data["start_date"]:
            raise ValidationError(_("El final no puede ser anterior al inicio."))
    elif data["ends_at"] < data["starts_at"]:
        raise ValidationError(_("El final no puede ser anterior al inicio."))


def _normalize(data):
    """Deja solo los campos de fecha que corresponden (día completo u hora)."""
    if data.get("all_day"):
        data["starts_at"] = data["ends_at"] = None
    else:
        data["start_date"] = data["end_date"] = None
    data["title"] = " ".join((data.get("title") or "").split())
    if not data["title"]:
        raise ValidationError(_("Escribe el título del evento."))
    return data


def create_event(household, user, **data) -> Event:
    data = _normalize(data)
    _check(household, user, data)
    participants = data.pop("participants", [])
    event = Event.objects.create(household=household, owner=user, **data)
    event.participants.set(participants)
    return event


def update_event(event: Event, user, **data) -> Event:
    if not event.can_edit(user):
        raise PermissionDenied
    data.pop("visibility", None)
    data = _normalize(data)
    _check(event.household, event.owner, {**data, "visibility": event.visibility})
    participants = data.pop("participants", None)
    for name, value in data.items():
        setattr(event, name, value)
    event.save()
    if participants is not None:
        event.participants.set(participants)
    return event


def make_shared(event: Event, user) -> Event:
    if event.owner_id != user.pk:
        raise PermissionDenied
    event.visibility = Visibility.SHARED
    event.save(update_fields=["visibility", "updated_at"])
    return event


def delete_event(event: Event, user, membership) -> None:
    """Borra el evento (con todas sus repeticiones)."""
    if not event.can_delete(user, membership):
        raise PermissionDenied
    event.delete()


# --- Consulta del calendario --------------------------------------------------------------


@dataclass
class Item:
    """Algo que se pinta en un día: una repetición de un evento o una tarea con fecha."""

    type: str  # "event" | "task"
    obj: object
    day: date
    title: str
    url: str
    color: str
    dot: str
    all_day: bool = True
    start: datetime | None = None  # hora local (sin zona), solo eventos con hora
    end: datetime | None = None
    occurrence: date | None = None  # día de inicio de esta repetición
    continues: bool = False  # el evento empezó un día anterior
    done: bool = False
    participants: list = field(default_factory=list)

    @property
    def sort_key(self):
        return (0 if self.all_day else 1, self.start or datetime.min, self.title.lower())


def _local_naive(value: datetime) -> datetime:
    return timezone.localtime(value).replace(tzinfo=None)


def _expand(event: Event, start: date, end: date) -> list[Item]:
    """Elementos (uno por día cubierto) de las repeticiones que tocan el rango."""
    if event.all_day:
        first = datetime.combine(event.start_date, time())
        duration = timedelta(days=(event.end_date - event.start_date).days)
    else:
        first = _local_naive(event.starts_at)
        duration = _local_naive(event.ends_at) - first

    window_start = datetime.combine(start, time()) - duration
    window_end = datetime.combine(end, time.max)
    if event.recurrence_rule:
        starts = recurrence.between(event.recurrence_rule, first, window_start, window_end)
    else:
        starts = [first] if window_start <= first <= window_end else []

    participants = list(event.participants.all())
    url = reverse("calendar:detail", args=[event.pk])
    items = []
    for occ in starts:
        occ_end = occ + duration
        last_day = occ_end.date()
        if not event.all_day and occ_end > occ and occ_end.time() == time():
            last_day -= timedelta(days=1)  # acaba a medianoche: no ocupa el día siguiente
        day = max(occ.date(), start)
        while day <= min(last_day, end):
            items.append(
                Item(
                    type="event",
                    obj=event,
                    day=day,
                    title=event.title,
                    url=f"{url}?fecha={occ:%Y-%m-%d}",
                    color=KIND_COLORS[event.kind],
                    dot=KIND_DOTS[event.kind],
                    all_day=event.all_day or day != occ.date(),
                    start=None if event.all_day else occ,
                    end=None if event.all_day else occ_end,
                    occurrence=occ.date(),
                    continues=day != occ.date(),
                    participants=participants,
                )
            )
            day += timedelta(days=1)
    return items


def items_between(user, household, start: date, end: date) -> dict[date, list[Item]]:
    """{día: [elementos ordenados]} para cada día del rango (ambos incluidos)."""
    if (end - start).days > MAX_RANGE_DAYS:
        raise ValueError("Rango demasiado grande")
    tz = timezone.get_current_timezone()
    range_start = datetime.combine(start, time(), tzinfo=tz)
    range_end = datetime.combine(end + timedelta(days=1), time(), tzinfo=tz)

    events = events_for(user, household).filter(
        # Con repetición: cualquiera que haya empezado antes del final del rango.
        Q(~Q(recurrence_rule=""), all_day=True, start_date__lte=end)
        | Q(~Q(recurrence_rule=""), all_day=False, starts_at__lt=range_end)
        # Sin repetición: los que se solapan con el rango.
        | Q(recurrence_rule="", all_day=True, start_date__lte=end, end_date__gte=start)
        | Q(recurrence_rule="", all_day=False, starts_at__lt=range_end, ends_at__gte=range_start)
    )
    days: dict[date, list[Item]] = {
        start + timedelta(days=n): [] for n in range((end - start).days + 1)
    }
    for event in events:
        for item in _expand(event, start, end):
            days[item.day].append(item)

    tasks = (
        Task.objects.visible_to(user, household)
        .filter(due_date__gte=start, due_date__lte=end)
        .select_related("assignee")
    )
    for task in tasks:
        days[task.due_date].append(
            Item(
                type="task",
                obj=task,
                day=task.due_date,
                title=task.title,
                url=reverse("tasks:detail", args=[task.pk]),
                color=TASK_COLOR,
                dot=TASK_DOT,
                done=task.is_done,
                participants=[task.assignee] if task.assignee else [],
            )
        )
    for items in days.values():
        items.sort(key=lambda i: i.sort_key)
    return days


def dashboard_summary(user, household) -> dict:
    """Eventos de hoy para el inicio."""
    today = timezone.localdate()
    items = items_between(user, household, today, today)[today]
    return {"today_events": [i for i in items if i.type == "event"]}
