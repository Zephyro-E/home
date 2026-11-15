"""Compras: lista de la compra cotidiana y deseos (personales o propuestas comunes).

Todos los modelos de dominio heredan de HouseholdOwnedModel (ADR-005).
"""

from django.conf import settings
from django.db import models
from django.db.models import Count, F, Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import HouseholdOwnedModel, HouseholdOwnedQuerySet, Visibility


class GroceryItem(HouseholdOwnedModel):
    """Producto de la lista de la compra. Siempre compartido con el hogar.

    `owner` es quien lo añadió.
    """

    name = models.CharField(_("producto"), max_length=120)
    quantity = models.CharField(_("cantidad"), max_length=40, blank=True)
    is_checked = models.BooleanField(default=False)
    checked_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["is_checked", "created_at"]
        verbose_name = _("producto de la lista")
        verbose_name_plural = _("lista de la compra")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.visibility = Visibility.SHARED  # la lista siempre es del hogar
        super().save(*args, **kwargs)


class WishQuerySet(HouseholdOwnedQuerySet):
    def with_stats(self):
        """Añade puntuación de votos (`score`), votos a favor/en contra y nº de comentarios."""
        # Count(distinct=True) evita que la unión con comentarios multiplique los votos.
        return self.annotate(
            up_count=Count("votes", filter=Q(votes__value=1), distinct=True),
            down_count=Count("votes", filter=Q(votes__value=-1), distinct=True),
            comment_count=Count("comments", distinct=True),
        ).annotate(score=F("up_count") - F("down_count"))


class WishItem(HouseholdOwnedModel):
    """Deseo personal (privado) o propuesta de compra común (compartida)."""

    class Priority(models.TextChoices):
        LOW = "low", _("Baja")
        MEDIUM = "medium", _("Media")
        HIGH = "high", _("Alta")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente")
        APPROVED = "approved", _("Aprobado")
        BOUGHT = "bought", _("Comprado")
        DISCARDED = "discarded", _("Descartado")

    ACTIVE_STATUSES = (Status.PENDING, Status.APPROVED)

    name = models.CharField(_("nombre"), max_length=150)
    description = models.TextField(_("descripción"), blank=True)
    estimated_price_cents = models.PositiveBigIntegerField(_("precio aproximado"), null=True)
    url = models.URLField(_("enlace"), max_length=500, blank=True)
    image_url = models.URLField(_("imagen (enlace)"), max_length=500, blank=True)
    priority = models.CharField(
        _("prioridad"), max_length=8, choices=Priority, default=Priority.MEDIUM
    )
    status = models.CharField(_("estado"), max_length=10, choices=Status, default=Status.PENDING)
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)

    objects = WishQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("deseo")
        verbose_name_plural = _("deseos")

    def __str__(self):
        return self.name

    @property
    def is_shared(self) -> bool:
        return self.visibility == Visibility.SHARED

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES


class WishVote(models.Model):
    """Voto de una persona sobre una propuesta común. Retirar el voto = borrar la fila."""

    class Value(models.IntegerChoices):
        UP = 1, _("A favor")
        DOWN = -1, _("En contra")

    item = models.ForeignKey(WishItem, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    value = models.SmallIntegerField(choices=Value)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "user"], name="shopping_one_vote_per_user"),
            models.CheckConstraint(condition=Q(value__in=[1, -1]), name="shopping_vote_value"),
        ]

    def __str__(self):
        return f"{self.user} {self.value:+d} {self.item}"


class WishComment(models.Model):
    item = models.ForeignKey(WishItem, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    body = models.TextField(_("comentario"), max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.body[:50]
