"""Lógica de películas y series."""

import random

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.core import social
from apps.core.models import Visibility
from apps.notifications.services import notify

from .models import SeriesProgress, Title, TitleComment, TitleRating

FILTERS = {
    "por-ver": (Title.Status.PENDING,),
    "viendo": (Title.Status.WATCHING,),
    "vistas": (Title.Status.WATCHED,),
    "abandonadas": (Title.Status.DROPPED,),
}


def titles_for(user, household):
    return Title.objects.visible_to(user, household).select_related("owner")


def listing(user, household, status="por-ver", kind="", query=""):
    qs = titles_for(user, household).filter(status__in=FILTERS.get(status, FILTERS["por-ver"]))
    if kind in Title.Kind.values:
        qs = qs.filter(kind=kind)
    if query:
        qs = qs.filter(
            Q(title__icontains=query) | Q(genre__icontains=query) | Q(platform__icontains=query)
        )
    qs = social.with_rating(qs, TitleRating, "title").annotate(
        comment_count=Count("comments", distinct=True)
    )
    return qs.order_by("-created_at")


def _clean_title(data):
    data["title"] = " ".join((data.get("title") or "").split())
    if not data["title"]:
        raise ValidationError(_("Escribe el título."))
    return data


def create_title(household, user, **data) -> Title:
    return Title.objects.create(household=household, owner=user, **_clean_title(data))


def update_title(item: Title, user, **data) -> Title:
    if not item.can_edit(user):
        raise PermissionDenied
    data.pop("visibility", None)
    for name, value in _clean_title(data).items():
        setattr(item, name, value)
    item.save()
    return item


def set_status(item: Title, user, status: str) -> Title:
    if not item.can_edit(user):
        raise PermissionDenied
    if status not in Title.Status.values:
        raise ValidationError(_("Estado no válido."))
    item.status = status
    item.save(update_fields=["status", "updated_at"])
    return item


def make_shared(item: Title, user) -> Title:
    if item.owner_id != user.pk:
        raise PermissionDenied
    item.visibility = Visibility.SHARED
    item.save(update_fields=["visibility", "updated_at"])
    return item


def delete_title(item: Title, user, membership) -> None:
    if not item.can_delete(user, membership):
        raise PermissionDenied
    item.delete()


def rate(item: Title, user, stars: int):
    return social.rate(TitleRating, "title", item, user, stars)


def add_comment(item: Title, user, body: str):
    comment = social.add_comment(TitleComment, "title", item, user, body)
    url = reverse("media:detail", args=[item.pk])
    notify(item.household, [item.owner], user, "comment", item.title, url)
    return comment


def set_progress(item: Title, user, season: int, episode: int) -> SeriesProgress:
    """Guarda por dónde va la persona. Al apuntar progreso, una serie "por ver" pasa a
    "viendo"."""
    if not item.is_series:
        raise ValidationError(_("El progreso solo se apunta en series."))
    if not (1 <= season <= 99 and 0 <= episode <= 999):
        raise ValidationError(_("Temporada o episodio no válidos."))
    progress, _created = SeriesProgress.objects.update_or_create(
        title=item, user=user, defaults={"season": season, "episode": episode}
    )
    if item.status == Title.Status.PENDING and item.can_edit(user):
        set_status(item, user, Title.Status.WATCHING)
    return progress


def next_episode(item: Title, user) -> SeriesProgress:
    current = SeriesProgress.objects.filter(title=item, user=user).first()
    season, episode = (current.season, current.episode) if current else (1, 0)
    return set_progress(item, user, season, min(episode + 1, 999))


def pick_random(user, household, kind="", exclude=None) -> Title | None:
    """Algo "por ver" al azar (opcionalmente película o serie), distinto del anterior."""
    qs = titles_for(user, household).filter(status=Title.Status.PENDING)
    if kind in Title.Kind.values:
        qs = qs.filter(kind=kind)
    ids = list(qs.values_list("pk", flat=True))
    if exclude and len(ids) > 1 and exclude in ids:
        ids.remove(exclude)
    return qs.get(pk=random.choice(ids)) if ids else None
