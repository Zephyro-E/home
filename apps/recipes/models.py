"""Recetario del hogar: recetas con ingredientes, pasos, raciones, foto y valoraciones."""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import HouseholdOwnedModel
from apps.core.social import AbstractComment, AbstractRating


def recipe_image_path(instance, filename):
    # Nombre aleatorio: no revela nada y no choca con otros archivos.
    return f"recipes/{instance.household_id}/{uuid.uuid4().hex}.webp"


class Recipe(HouseholdOwnedModel):
    class Course(models.TextChoices):
        STARTER = "starter", _("Entrante")
        MAIN = "main", _("Principal")
        DESSERT = "dessert", _("Postre")
        BREAKFAST = "breakfast", _("Desayuno")
        SNACK = "snack", _("Merienda o picoteo")
        OTHER = "other", _("Otro")

    title = models.CharField(_("título"), max_length=200)
    course = models.CharField(
        _("tipo de plato"), max_length=10, choices=Course, default=Course.MAIN
    )
    description = models.TextField(_("descripción"), blank=True)
    servings = models.PositiveSmallIntegerField(_("raciones"), default=4)
    prep_minutes = models.PositiveSmallIntegerField(_("preparación (min)"), null=True, blank=True)
    cook_minutes = models.PositiveSmallIntegerField(_("cocción (min)"), null=True, blank=True)
    instructions = models.TextField(_("pasos"), blank=True)
    tags = models.CharField(_("etiquetas"), max_length=200, blank=True)
    source_url = models.URLField(_("receta original (enlace)"), max_length=500, blank=True)
    image = models.ImageField(_("foto"), upload_to=recipe_image_path, blank=True)

    class Meta:
        ordering = ["title"]
        verbose_name = _("receta")
        verbose_name_plural = _("recetas")

    def __str__(self):
        return self.title

    @property
    def total_minutes(self):
        total = (self.prep_minutes or 0) + (self.cook_minutes or 0)
        return total or None

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def steps(self) -> list[str]:
        """Un paso por línea (las líneas vacías se ignoran)."""
        return [line.strip() for line in self.instructions.splitlines() if line.strip()]


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ingredients")
    position = models.PositiveSmallIntegerField(default=0)
    quantity = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.name


class RecipeRating(AbstractRating):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="ratings")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["recipe", "user"], name="recipes_one_rating_per_user"),
            models.CheckConstraint(
                condition=models.Q(stars__gte=1, stars__lte=5), name="recipes_stars_1_5"
            ),
        ]


class RecipeComment(AbstractComment):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="comments")

    class Meta(AbstractComment.Meta):
        pass
