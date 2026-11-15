"""Sitios que queremos visitar (restaurantes, excursiones, viajes…)."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import HouseholdOwnedModel
from apps.core.social import AbstractComment, AbstractRating


class Place(HouseholdOwnedModel):
    class Category(models.TextChoices):
        RESTAURANT = "restaurant", _("Restaurante")
        BAR = "bar", _("Bar o cafetería")
        CULTURE = "culture", _("Museo o cultura")
        NATURE = "nature", _("Naturaleza o excursión")
        TRIP = "trip", _("Viaje o ciudad")
        SHOP = "shop", _("Tienda")
        LEISURE = "leisure", _("Ocio")
        OTHER = "other", _("Otro")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente")
        VISITED = "visited", _("Visitado")

    name = models.CharField(_("nombre"), max_length=200)
    category = models.CharField(
        _("categoría"), max_length=12, choices=Category, default=Category.RESTAURANT
    )
    location = models.CharField(_("dirección o zona"), max_length=250, blank=True)
    description = models.TextField(_("notas"), blank=True)
    url = models.URLField(_("enlace"), max_length=500, blank=True)
    image_url = models.URLField(_("imagen (enlace)"), max_length=500, blank=True)
    status = models.CharField(_("estado"), max_length=8, choices=Status, default=Status.PENDING)
    visited_on = models.DateField(_("fecha de la visita"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("sitio")
        verbose_name_plural = _("sitios")

    def __str__(self):
        return self.name


class PlaceRating(AbstractRating):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="ratings")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["place", "user"], name="places_one_rating_per_user"),
            models.CheckConstraint(
                condition=models.Q(stars__gte=1, stars__lte=5), name="places_stars_1_5"
            ),
        ]


class PlaceComment(AbstractComment):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="comments")

    class Meta(AbstractComment.Meta):
        pass


CATEGORY_ICONS = {
    Place.Category.RESTAURANT: "chef-hat",
    Place.Category.BAR: "users-round",
    Place.Category.CULTURE: "clapperboard",
    Place.Category.NATURE: "map",
    Place.Category.TRIP: "map-pin",
    Place.Category.SHOP: "shopping-cart",
    Place.Category.LEISURE: "star",
    Place.Category.OTHER: "map-pin",
}
