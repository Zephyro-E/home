"""Lógica del recetario."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext as _

from apps.core import images, social
from apps.core.models import Visibility
from apps.shopping import services as shopping

from . import ingredients as ing
from .models import Recipe, RecipeComment, RecipeIngredient, RecipeRating

MAX_SERVINGS = 50


def recipes_for(user, household):
    return Recipe.objects.visible_to(user, household).select_related("owner")


def listing(user, household, query="", course="", tag=""):
    qs = recipes_for(user, household)
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(tags__icontains=query)
            | Q(ingredients__name__icontains=query)
        ).distinct()
    if course in Recipe.Course.values:
        qs = qs.filter(course=course)
    if tag:
        qs = qs.filter(tags__icontains=tag)
    qs = social.with_rating(qs, RecipeRating, "recipe").annotate(
        ingredient_count=Count("ingredients", distinct=True)
    )
    return qs.order_by("title")


def all_tags(user, household) -> list[str]:
    tags = set()
    for text in recipes_for(user, household).exclude(tags="").values_list("tags", flat=True):
        tags.update(t.strip() for t in text.split(",") if t.strip())
    return sorted(tags, key=str.lower)


def _clean(data):
    data["title"] = " ".join((data.get("title") or "").split())
    if not data["title"]:
        raise ValidationError(_("Escribe el título de la receta."))
    servings = data.get("servings")
    if servings is None:
        servings = data["servings"] = 4
    if not 1 <= servings <= MAX_SERVINGS:
        raise ValidationError(_("Las raciones deben estar entre 1 y 50."))
    tags = [" ".join(t.split()) for t in (data.get("tags") or "").split(",")]
    data["tags"] = ", ".join(dict.fromkeys(t for t in tags if t))[:200]
    return data


def _save_ingredients(recipe, text):
    recipe.ingredients.all().delete()
    RecipeIngredient.objects.bulk_create(
        RecipeIngredient(recipe=recipe, position=i, **item)
        for i, item in enumerate(ing.parse_text(text))
    )


@transaction.atomic
def create_recipe(household, user, ingredients_text="", image=None, **data) -> Recipe:
    recipe = Recipe.objects.create(household=household, owner=user, **_clean(data))
    _save_ingredients(recipe, ingredients_text)
    if image:
        images.replace_image(recipe, "image", image)
    return recipe


@transaction.atomic
def update_recipe(recipe, user, ingredients_text=None, image=None, remove_image=False, **data):
    if not recipe.can_edit(user):
        raise PermissionDenied
    data.pop("visibility", None)
    for name, value in _clean(data).items():
        setattr(recipe, name, value)
    recipe.save()
    if ingredients_text is not None:
        _save_ingredients(recipe, ingredients_text)
    if image:
        images.replace_image(recipe, "image", image)
    elif remove_image:
        images.remove_image(recipe, "image")
    return recipe


def ingredients_text(recipe) -> str:
    return "\n".join(ing.to_line(i.quantity, i.unit, i.name) for i in recipe.ingredients.all())


def make_shared(recipe, user):
    if recipe.owner_id != user.pk:
        raise PermissionDenied
    recipe.visibility = Visibility.SHARED
    recipe.save(update_fields=["visibility", "updated_at"])
    return recipe


def delete_recipe(recipe, user, membership) -> None:
    if not recipe.can_delete(user, membership):
        raise PermissionDenied
    if recipe.image:
        recipe.image.delete(save=False)
    recipe.delete()


def scaled_ingredients(recipe, servings: int):
    """Ingredientes para `servings` raciones: [(ingrediente, cantidad escalada, línea)]."""
    factor = Decimal(servings) / Decimal(recipe.servings or 1)
    rows = []
    for item in recipe.ingredients.all():
        qty = ing.scale(item.quantity, factor)
        rows.append((item, qty, ing.to_line(qty, item.unit, item.name)))
    return rows


def add_to_grocery(recipe, user, household, servings: int, ingredient_ids) -> int:
    """Añade a la lista de la compra los ingredientes elegidos, con la cantidad escalada.

    Si el producto ya está en la lista, la cantidad se actualiza (ver add_grocery).
    """
    chosen = set(ingredient_ids)
    added = 0
    for item, qty, _line in scaled_ingredients(recipe, servings):
        if item.pk not in chosen:
            continue
        quantity = " ".join(p for p in (ing.format_quantity(qty), item.unit) if p)
        shopping.add_grocery(household, user, item.name, quantity[:40])
        added += 1
    return added


def rate(recipe, user, stars):
    return social.rate(RecipeRating, "recipe", recipe, user, stars)


def add_comment(recipe, user, body):
    return social.add_comment(RecipeComment, "recipe", recipe, user, body)
