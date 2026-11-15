"""Buscador global: busca un texto en todos los módulos.

Cada búsqueda parte de las funciones *_for de cada módulo, que aplican visible_to
(ADR-005): solo aparece lo que la persona puede ver.
"""

from dataclasses import dataclass, field

from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.money import format_euros

MIN_LENGTH = 2
PER_GROUP = 8


@dataclass
class Group:
    key: str
    label: str
    icon: str
    items: list = field(default_factory=list)  # [(título, detalle, url)]
    more_url: str = ""


def search(user, household, query: str) -> list[Group]:
    query = " ".join((query or "").split())[:100]
    if len(query) < MIN_LENGTH or household is None:
        return []
    groups = [builder(user, household, query) for builder in BUILDERS]
    return [g for g in groups if g.items]


def _grocery(user, household, q):
    from apps.shopping.services import grocery_for

    qs = grocery_for(user, household).filter(name__icontains=q)[:PER_GROUP]
    url = reverse("shopping:list")
    return Group(
        "grocery",
        _("Lista de la compra"),
        "shopping-cart",
        [(g.name, g.quantity, url) for g in qs],
    )


def _wishes(user, household, q):
    from apps.shopping.services import wishes_for

    qs = wishes_for(user, household).filter(Q(name__icontains=q) | Q(description__icontains=q))
    return Group(
        "wishes",
        _("Deseos"),
        "gift",
        [
            (w.name, w.get_status_display(), reverse("shopping:wish_detail", args=[w.pk]))
            for w in qs[:PER_GROUP]
        ],
    )


def _tasks(user, household, q):
    from apps.tasks.services import tasks_for

    qs = tasks_for(user, household).filter(Q(title__icontains=q) | Q(description__icontains=q))
    return Group(
        "tasks",
        _("Tareas"),
        "list-checks",
        [
            (t.title, t.get_status_display(), reverse("tasks:detail", args=[t.pk]))
            for t in qs.order_by("status", "-created_at")[:PER_GROUP]
        ],
    )


def _events(user, household, q):
    from apps.events.services import events_for

    qs = events_for(user, household).filter(
        Q(title__icontains=q) | Q(location__icontains=q) | Q(description__icontains=q)
    )
    items = []
    for e in qs.order_by("-start_date", "-starts_at")[:PER_GROUP]:
        items.append(
            (e.title, e.first_day.strftime("%d/%m/%Y"), reverse("calendar:detail", args=[e.pk]))
        )
    return Group("events", _("Calendario"), "calendar", items)


def _media(user, household, q):
    from apps.media.services import titles_for

    qs = titles_for(user, household).filter(
        Q(title__icontains=q) | Q(genre__icontains=q) | Q(platform__icontains=q)
    )
    return Group(
        "media",
        _("Películas y series"),
        "clapperboard",
        [
            (t.title, t.get_kind_display(), reverse("media:detail", args=[t.pk]))
            for t in qs[:PER_GROUP]
        ],
    )


def _places(user, household, q):
    from apps.places.services import places_for

    qs = places_for(user, household).filter(
        Q(name__icontains=q) | Q(location__icontains=q) | Q(description__icontains=q)
    )
    return Group(
        "places",
        _("Sitios"),
        "map-pin",
        [
            (p.name, p.location or p.get_category_display(), reverse("places:detail", args=[p.pk]))
            for p in qs[:PER_GROUP]
        ],
    )


def _recipes(user, household, q):
    from apps.recipes.services import recipes_for

    qs = recipes_for(user, household).filter(
        Q(title__icontains=q) | Q(tags__icontains=q) | Q(ingredients__name__icontains=q)
    )
    return Group(
        "recipes",
        _("Recetas"),
        "chef-hat",
        [
            (r.title, r.get_course_display(), reverse("recipes:detail", args=[r.pk]))
            for r in qs.distinct()[:PER_GROUP]
        ],
    )


def _finance(user, household, q):
    from apps.finance.services import transactions_for

    qs = transactions_for(user, household).filter(
        Q(description__icontains=q) | Q(notes__icontains=q) | Q(category__name__icontains=q)
    )
    items = []
    for t in qs[:PER_GROUP]:
        title = t.description or (t.category.name if t.category else t.get_kind_display())
        detail = f"{t.date:%d/%m/%Y} · {format_euros(t.amount_cents)}"
        url = reverse("finance:transaction_edit", args=[t.pk]) if t.can_edit(user) else ""
        items.append((title, detail, url or reverse("finance:transactions")))
    return Group("finance", _("Finanzas"), "wallet", items)


BUILDERS = [_grocery, _tasks, _events, _wishes, _recipes, _media, _places, _finance]
