"""Registro de módulos de la aplicación.

Es la fuente única para el dashboard y la navegación. Cuando un módulo se implementa,
basta con rellenar su `url_name`; mientras sea `None` se muestra como "Próximamente".

Las clases de color se escriben completas para que Tailwind las detecte al compilar.
"""

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    description: str
    icon: str
    color: str  # clases Tailwind para el icono
    phase: int
    url_name: str | None = None
    in_bottom_nav: bool = False

    @property
    def enabled(self) -> bool:
        return self.url_name is not None

    @property
    def url(self) -> str | None:
        return reverse(self.url_name) if self.url_name else None


MODULES: list[Module] = [
    Module(
        "shopping",
        _("Compras"),
        _("Lista de la compra y deseos"),
        "shopping-cart",
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
        phase=2,
        url_name="shopping:list",
        in_bottom_nav=True,
    ),
    Module(
        "tasks",
        _("Tareas"),
        _("Tablero de tareas del hogar"),
        "list-checks",
        "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
        phase=3,
        url_name="tasks:board",
        in_bottom_nav=True,
    ),
    Module(
        "calendar",
        _("Calendario"),
        _("Eventos, citas y cumpleaños"),
        "calendar",
        "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
        phase=4,
        in_bottom_nav=True,
    ),
    Module(
        "media",
        _("Películas y series"),
        _("Qué ver y qué hemos visto"),
        "clapperboard",
        "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
        phase=5,
    ),
    Module(
        "places",
        _("Sitios"),
        _("Lugares que queremos visitar"),
        "map-pin",
        "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
        phase=5,
    ),
    Module(
        "finance",
        _("Finanzas"),
        _("Gastos, presupuestos y ahorro"),
        "wallet",
        "bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
        phase=6,
    ),
    Module(
        "recipes",
        _("Recetas"),
        _("Recetario del hogar"),
        "chef-hat",
        "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
        phase=8,
    ),
]
