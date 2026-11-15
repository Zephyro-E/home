"""Vistas del calendario: mes, semana, agenda y eventos. Todo parte de visible_to."""

import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import HouseholdRequiredMixin
from apps.core.models import Membership

from . import services
from .forms import EventForm
from .models import KIND_COLORS, Event

AGENDA_DAYS = 60


MIN_YEAR, MAX_YEAR = 1900, 2200  # fuera de aquí, la fecha se ignora


def _parse_date(text, default: date) -> date:
    try:
        value = date.fromisoformat(text) if text else default
    except ValueError:
        return default
    return value if value is None or MIN_YEAR <= value.year <= MAX_YEAR else default


def _parse_month(text, default: date) -> date:
    try:
        year, month = (int(p) for p in (text or "").split("-"))
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise ValueError
        return date(year, month, 1)
    except ValueError:
        return default.replace(day=1)


def _member_colors(household) -> dict:
    return dict(Membership.objects.filter(household=household).values_list("user_id", "color"))


def _add_months(first: date, n: int) -> date:
    month = first.month - 1 + n
    return date(first.year + month // 12, month % 12 + 1, 1)


class CalendarMixin(HouseholdRequiredMixin):
    def common(self, view):
        return {
            "today": timezone.localdate(),
            "view": view,
            "colors": _member_colors(self.request.household),
        }


class MonthView(CalendarMixin, TemplateView):
    template_name = "events/month.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        first = _parse_month(self.request.GET.get("mes"), today)
        in_month = (first.year, first.month) == (today.year, today.month)
        selected = _parse_date(self.request.GET.get("dia"), today if in_month else first)
        if (selected.year, selected.month) != (first.year, first.month):
            selected = first
        # Cuadrícula de semanas completas, de lunes a domingo.
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
        days = services.items_between(
            self.request.user, self.request.household, weeks[0][0], weeks[-1][-1]
        )
        context.update(self.common("month"))
        context.update(
            month=first,
            weeks=[[(day, days[day]) for day in week] for week in weeks],
            selected=selected,
            selected_items=days.get(selected, []),
            prev_month=_add_months(first, -1),
            next_month=_add_months(first, 1),
            weekdays=[weeks[0][i] for i in range(7)],
        )
        return context


class WeekView(CalendarMixin, TemplateView):
    template_name = "events/week.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        day = _parse_date(self.request.GET.get("dia"), today)
        monday = day - timedelta(days=day.weekday())
        sunday = monday + timedelta(days=6)
        days = services.items_between(self.request.user, self.request.household, monday, sunday)
        context.update(self.common("week"))
        context.update(
            days=list(days.items()),
            monday=monday,
            sunday=sunday,
            prev_week=monday - timedelta(days=7),
            next_week=monday + timedelta(days=7),
        )
        return context


class AgendaView(CalendarMixin, TemplateView):
    template_name = "events/agenda.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        days = services.items_between(
            self.request.user, self.request.household, today, today + timedelta(days=AGENDA_DAYS)
        )
        context.update(self.common("agenda"))
        context.update(
            days=[(d, items) for d, items in days.items() if items],
            until=today + timedelta(days=AGENDA_DAYS),
        )
        return context


# --- Eventos ------------------------------------------------------------------------------


class EventMixin(HouseholdRequiredMixin):
    def get_event(self, pk):
        return get_object_or_404(
            services.events_for(self.request.user, self.request.household), pk=pk
        )

    def form(self, data=None, **kwargs):
        return EventForm(data, household=self.request.household, user=self.request.user, **kwargs)


class EventCreateView(EventMixin, View):
    template_name = "events/event_form.html"

    def get(self, request):
        day = _parse_date(request.GET.get("fecha"), timezone.localdate())
        initial = {"start_date": day, "kind": Event.Kind.GENERAL, "visibility": "shared"}
        return render(request, self.template_name, {"form": self.form(initial=initial)})

    def post(self, request):
        form = self.form(request.POST)
        if form.is_valid():
            try:
                event = services.create_event(request.household, request.user, **form.event_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Evento guardado."))
                return redirect("calendar:detail", pk=event.pk)
        return render(request, self.template_name, {"form": form}, status=400)


class EventEditView(EventMixin, View):
    template_name = "events/event_form.html"

    def get_editable(self, pk):
        event = self.get_event(pk)
        if not event.can_edit(self.request.user):
            raise Http404
        return event

    def get(self, request, pk):
        event = self.get_editable(pk)
        return render(request, self.template_name, {"form": self.form(event=event), "event": event})

    def post(self, request, pk):
        event = self.get_editable(pk)
        form = self.form(request.POST, event=event)
        if form.is_valid():
            try:
                services.update_event(event, request.user, **form.event_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("calendar:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "event": event}, status=400)


class EventDetailView(EventMixin, TemplateView):
    template_name = "events/event_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.get_event(self.kwargs["pk"])
        occurrence = _parse_date(self.request.GET.get("fecha"), None)
        context.update(
            event=event,
            occurrence=occurrence,
            kind_color=KIND_COLORS[event.kind],
            can_edit=event.can_edit(self.request.user),
            can_delete=event.can_delete(self.request.user, self.request.membership),
            colors=_member_colors(self.request.household),
            participants=list(event.participants.all()),
            local_start=timezone.localtime(event.starts_at) if event.starts_at else None,
            local_end=timezone.localtime(event.ends_at) if event.ends_at else None,
        )
        return context


class EventShareView(EventMixin, View):
    def post(self, request, pk):
        services.make_shared(self.get_event(pk), request.user)
        messages.success(request, _("Ahora el evento es del hogar: el resto ya lo ve."))
        return redirect("calendar:detail", pk=pk)


class EventDeleteView(EventMixin, View):
    def post(self, request, pk):
        services.delete_event(self.get_event(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        messages.success(request, _("Evento borrado."))
        return redirect("calendar:month")
