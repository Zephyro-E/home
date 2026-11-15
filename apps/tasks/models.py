"""Tareas del hogar: tablero Pendiente / En curso / Terminada.

Task y TaskLabel heredan de HouseholdOwnedModel (ADR-005). Subtareas y comentarios
cuelgan de una tarea y se acceden siempre a través de ella.
"""

from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import (
    MEMBER_COLORS,
    HouseholdOwnedModel,
    HouseholdOwnedQuerySet,
    Visibility,
)


class TaskLabel(HouseholdOwnedModel):
    """Etiqueta de tareas, común a todo el hogar."""

    name = models.CharField(_("nombre"), max_length=40)
    color = models.CharField(_("color"), max_length=12, default="teal")

    class Meta:
        ordering = ["name"]
        verbose_name = _("etiqueta")
        verbose_name_plural = _("etiquetas")
        constraints = [
            models.UniqueConstraint(fields=["household", "name"], name="tasks_unique_label_name")
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.visibility = Visibility.SHARED
        if self.color not in MEMBER_COLORS:
            self.color = MEMBER_COLORS[0]
        super().save(*args, **kwargs)


class TaskQuerySet(HouseholdOwnedQuerySet):
    def with_counts(self):
        return self.annotate(
            subtask_count=Count("subtasks", distinct=True),
            subtask_done=Count("subtasks", filter=Q(subtasks__is_done=True), distinct=True),
            comment_count=Count("comments", distinct=True),
        )


class Task(HouseholdOwnedModel):
    class Status(models.TextChoices):
        TODO = "todo", _("Pendiente")
        DOING = "doing", _("En curso")
        DONE = "done", _("Terminada")

    class Priority(models.TextChoices):
        LOW = "low", _("Baja")
        MEDIUM = "medium", _("Media")
        HIGH = "high", _("Alta")

    title = models.CharField(_("título"), max_length=200)
    description = models.TextField(_("descripción"), blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("responsable"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    status = models.CharField(_("estado"), max_length=8, choices=Status, default=Status.TODO)
    position = models.IntegerField(default=0)
    due_date = models.DateField(_("fecha límite"), null=True, blank=True)
    priority = models.CharField(
        _("prioridad"), max_length=8, choices=Priority, default=Priority.MEDIUM
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    labels = models.ManyToManyField(TaskLabel, blank=True, related_name="tasks")

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name = _("tarea")
        verbose_name_plural = _("tareas")
        indexes = [models.Index(fields=["household", "status", "position"])]

    def __str__(self):
        return self.title

    @property
    def is_done(self) -> bool:
        return self.status == self.Status.DONE

    @property
    def due_state(self) -> str:
        """'overdue', 'today', 'soon' (próximos 3 días), 'later' o '' (sin fecha o terminada)."""
        if not self.due_date or self.is_done:
            return ""
        delta = (self.due_date - timezone.localdate()).days
        if delta < 0:
            return "overdue"
        if delta == 0:
            return "today"
        return "soon" if delta <= 3 else "later"


class Subtask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(_("subtarea"), max_length=200)
    is_done = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.title


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    body = models.TextField(_("comentario"), max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.body[:50]
