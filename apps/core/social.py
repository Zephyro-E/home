"""Piezas comunes para valorar (1–5 estrellas por persona) y comentar elementos de módulos.

Cada módulo define sus modelos heredando de AbstractRating / AbstractComment y añadiendo
la clave foránea a su elemento con related_name="ratings" / "comments". Las plantillas
comunes son templates/partials/rating.html y templates/partials/comments.html.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Avg, Count, OuterRef, Subquery
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy


class AbstractRating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    stars = models.PositiveSmallIntegerField(gettext_lazy("estrellas"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AbstractComment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    body = models.TextField(gettext_lazy("comentario"), max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at"]

    def __str__(self):
        return self.body[:50]


def with_rating(queryset, rating_model, fk: str):
    """Añade `avg_stars` y `rating_count` con subconsultas (no se mezclan con otros
    recuentos ni pierden el orden)."""
    base = rating_model.objects.filter(**{fk: OuterRef("pk")}).values(fk)
    return queryset.annotate(
        avg_stars=Subquery(base.annotate(a=Avg("stars")).values("a")[:1]),
        rating_count=Subquery(base.annotate(c=Count("pk")).values("c")[:1]),
    )


@transaction.atomic
def rate(rating_model, fk: str, obj, user, stars: int) -> int | None:
    """Valora de 1 a 5. Repetir la misma puntuación la retira. Devuelve la resultante."""
    if stars not in range(1, 6):
        raise ValidationError(_("La valoración debe ser de 1 a 5 estrellas."))
    current = rating_model.objects.filter(**{fk: obj, "user": user}).first()
    if current and current.stars == stars:
        current.delete()
        return None
    if current:
        current.stars = stars
        current.save(update_fields=["stars", "updated_at"])
    else:
        rating_model.objects.create(**{fk: obj, "user": user, "stars": stars})
    return stars


def rating_context(obj, user) -> dict:
    """Datos para templates/partials/rating.html."""
    ratings = list(obj.ratings.select_related("user").order_by("-stars", "created_at"))
    mine = next((r.stars for r in ratings if r.user_id == user.pk), None)
    average = sum(r.stars for r in ratings) / len(ratings) if ratings else None
    return {"ratings": ratings, "my_stars": mine, "avg_stars": average}


def add_comment(comment_model, fk: str, obj, user, body: str):
    body = (body or "").strip()
    if not body:
        raise ValidationError(_("Escribe un comentario."))
    return comment_model.objects.create(**{fk: obj, "author": user, "body": body[:2000]})


def delete_comment(comment, user) -> None:
    if comment.author_id != user.pk:
        raise PermissionDenied
    comment.delete()
