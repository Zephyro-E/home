"""Avisos internos: "Luis te ha asignado una tarea", "Ana ha comentado en…".

Cada aviso es personal (visibility=private, owner = quien lo recibe), así que el patrón
común visible_to garantiza que nadie ve los avisos de otra persona (ADR-005).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import HouseholdOwnedModel, Visibility


class Notification(HouseholdOwnedModel):
    class Kind(models.TextChoices):
        TASK_ASSIGNED = "task_assigned", _("Tarea asignada")
        COMMENT = "comment", _("Comentario")
        WISH_PROPOSED = "wish_proposed", _("Propuesta de compra")
        EVENT_ADDED = "event_added", _("Evento")
        EXPENSE_SPLIT = "expense_split", _("Gasto compartido")
        SETTLEMENT = "settlement", _("Pago entre miembros")

    kind = models.CharField(max_length=20, choices=Kind)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    title = models.CharField(max_length=200)  # nombre del elemento (o importe)
    url = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "household", "read_at"])]

    def __str__(self):
        return f"{self.kind}: {self.title}"

    def save(self, *args, **kwargs):
        self.visibility = Visibility.PRIVATE
        super().save(*args, **kwargs)
