"""Lógica de sitios."""

import random

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import social
from apps.core.models import Visibility

from .models import Place, PlaceComment, PlaceRating

FILTERS = {"pendientes": Place.Status.PENDING, "visitados": Place.Status.VISITED}


def places_for(user, household):
    return Place.objects.visible_to(user, household).select_related("owner")


def listing(user, household, status="pendientes", category="", query=""):
    qs = places_for(user, household).filter(status=FILTERS.get(status, Place.Status.PENDING))
    if category in Place.Category.values:
        qs = qs.filter(category=category)
    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(location__icontains=query)
            | Q(description__icontains=query)
        )
    qs = social.with_rating(qs, PlaceRating, "place").annotate(
        comment_count=Count("comments", distinct=True)
    )
    order = "-visited_on" if status == "visitados" else "-created_at"
    return qs.order_by(order, "-created_at")


def _clean(data):
    data["name"] = " ".join((data.get("name") or "").split())
    if not data["name"]:
        raise ValidationError(_("Escribe el nombre del sitio."))
    if data.get("status") == Place.Status.PENDING:
        data["visited_on"] = None
    return data


def create_place(household, user, **data) -> Place:
    return Place.objects.create(household=household, owner=user, **_clean(data))


def update_place(place: Place, user, **data) -> Place:
    if not place.can_edit(user):
        raise PermissionDenied
    data.pop("visibility", None)
    for name, value in _clean(data).items():
        setattr(place, name, value)
    place.save()
    return place


def mark_visited(place: Place, user, visited: bool = True) -> Place:
    """Marca como visitado (con la fecha de hoy si no tenía) o lo devuelve a pendientes."""
    if not place.can_edit(user):
        raise PermissionDenied
    if visited:
        place.status = Place.Status.VISITED
        place.visited_on = place.visited_on or timezone.localdate()
    else:
        place.status = Place.Status.PENDING
        place.visited_on = None
    place.save(update_fields=["status", "visited_on", "updated_at"])
    return place


def make_shared(place: Place, user) -> Place:
    if place.owner_id != user.pk:
        raise PermissionDenied
    place.visibility = Visibility.SHARED
    place.save(update_fields=["visibility", "updated_at"])
    return place


def delete_place(place: Place, user, membership) -> None:
    if not place.can_delete(user, membership):
        raise PermissionDenied
    place.delete()


def rate(place: Place, user, stars: int):
    return social.rate(PlaceRating, "place", place, user, stars)


def add_comment(place: Place, user, body: str):
    return social.add_comment(PlaceComment, "place", place, user, body)


def pick_random(user, household, category="", exclude=None) -> Place | None:
    """Un sitio pendiente al azar (opcionalmente de una categoría), distinto del anterior."""
    qs = places_for(user, household).filter(status=Place.Status.PENDING)
    if category in Place.Category.values:
        qs = qs.filter(category=category)
    ids = list(qs.values_list("pk", flat=True))
    if exclude and len(ids) > 1 and exclude in ids:
        ids.remove(exclude)
    return qs.get(pk=random.choice(ids)) if ids else None
