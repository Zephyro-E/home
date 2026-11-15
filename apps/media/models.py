"""Películas y series: qué ver, qué estamos viendo y qué hemos visto."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import HouseholdOwnedModel
from apps.core.social import AbstractComment, AbstractRating


class Title(HouseholdOwnedModel):
    class Kind(models.TextChoices):
        MOVIE = "movie", _("Película")
        SERIES = "series", _("Serie")

    class Status(models.TextChoices):
        PENDING = "pending", _("Por ver")
        WATCHING = "watching", _("Viendo")
        WATCHED = "watched", _("Vista")
        DROPPED = "dropped", _("Abandonada")

    title = models.CharField(_("título"), max_length=200)
    kind = models.CharField(_("tipo"), max_length=8, choices=Kind, default=Kind.MOVIE)
    year = models.PositiveSmallIntegerField(_("año"), null=True, blank=True)
    genre = models.CharField(_("género"), max_length=60, blank=True)
    platform = models.CharField(_("dónde verla"), max_length=60, blank=True)
    synopsis = models.TextField(_("sinopsis"), blank=True)
    image_url = models.URLField(_("imagen (enlace)"), max_length=500, blank=True)
    url = models.URLField(_("enlace"), max_length=500, blank=True)
    status = models.CharField(_("estado"), max_length=10, choices=Status, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("título")
        verbose_name_plural = _("películas y series")

    def __str__(self):
        return self.title

    @property
    def is_series(self) -> bool:
        return self.kind == self.Kind.SERIES


class TitleRating(AbstractRating):
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="ratings")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["title", "user"], name="media_one_rating_per_user"),
            models.CheckConstraint(
                condition=models.Q(stars__gte=1, stars__lte=5), name="media_stars_1_5"
            ),
        ]


class TitleComment(AbstractComment):
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="comments")

    class Meta(AbstractComment.Meta):
        pass


class SeriesProgress(models.Model):
    """Por dónde va cada persona en una serie."""

    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="progress")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    season = models.PositiveSmallIntegerField(_("temporada"), default=1)
    episode = models.PositiveSmallIntegerField(_("episodio"), default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["title", "user"], name="media_one_progress_per_user")
        ]

    def __str__(self):
        return f"T{self.season} E{self.episode}"
