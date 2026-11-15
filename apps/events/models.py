"""Calendario: eventos con tipo, participantes y repetición (RRULE).

Los eventos de día completo usan fechas sin hora (start_date/end_date, ADR-008); los
demás, instantes en UTC (starts_at/ends_at) que se muestran en la zona del hogar.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import HouseholdOwnedModel
from apps.core.recurrence import describe


class Event(HouseholdOwnedModel):
    class Kind(models.TextChoices):
        GENERAL = "general", _("Evento")
        APPOINTMENT = "appointment", _("Cita")
        BIRTHDAY = "birthday", _("Cumpleaños")
        CELEBRATION = "celebration", _("Celebración")
        TRIP = "trip", _("Viaje")

    title = models.CharField(_("título"), max_length=200)
    kind = models.CharField(_("tipo"), max_length=12, choices=Kind, default=Kind.GENERAL)
    description = models.TextField(_("descripción"), blank=True)
    location = models.CharField(_("lugar"), max_length=200, blank=True)
    all_day = models.BooleanField(_("todo el día"), default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    recurrence_rule = models.CharField(_("repetición"), max_length=200, blank=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="+", verbose_name=_("participantes")
    )

    class Meta:
        ordering = ["start_date", "starts_at"]
        verbose_name = _("evento")
        verbose_name_plural = _("eventos")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(all_day=True, start_date__isnull=False, end_date__isnull=False)
                    | models.Q(all_day=False, starts_at__isnull=False, ends_at__isnull=False)
                ),
                name="events_dates_match_all_day",
            )
        ]

    def __str__(self):
        return self.title

    @property
    def first_day(self):
        """Primer día (en la zona del hogar)."""
        return self.start_date if self.all_day else timezone.localtime(self.starts_at).date()

    @property
    def recurrence_text(self) -> str:
        return describe(self.recurrence_rule)


# Clases completas para que Tailwind las incluya.
KIND_COLORS = {
    Event.Kind.GENERAL: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200",
    Event.Kind.APPOINTMENT: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
    Event.Kind.BIRTHDAY: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
    Event.Kind.CELEBRATION: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
    Event.Kind.TRIP: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
}
KIND_DOTS = {
    Event.Kind.GENERAL: "bg-violet-500",
    Event.Kind.APPOINTMENT: "bg-sky-500",
    Event.Kind.BIRTHDAY: "bg-rose-500",
    Event.Kind.CELEBRATION: "bg-amber-500",
    Event.Kind.TRIP: "bg-emerald-500",
}
TASK_COLOR = "bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-200"
TASK_DOT = "bg-stone-400"
