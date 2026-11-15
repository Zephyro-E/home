"""Etiquetas de plantilla reutilizables para la interfaz."""

import re
from functools import lru_cache

from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.core.money import format_euros

register = template.Library()

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.DOTALL)


@lru_cache(maxsize=128)
def _load_icon(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", name):
        return ""
    path = settings.BASE_DIR / "static" / "icons" / f"{name}.svg"
    if not path.exists():
        return ""
    return _COMMENT.sub("", path.read_text(encoding="utf-8")).strip()


@register.simple_tag
def icon(name: str, css: str = "size-5") -> str:
    """Inserta un icono Lucide en línea: {% icon "house" "size-6" %}.

    Los iconos viven en static/icons/ (lucide-static, licencia ISC).
    """
    svg = _load_icon(name)
    if not svg:
        return ""
    opening = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" class="{escape(css)}" aria-hidden="true" focusable="false">'
    )
    return mark_safe(_SVG_OPEN.sub(opening, svg, count=1))


# Clases completas (Tailwind solo incluye las que aparecen escritas literalmente).
MEMBER_COLOR_CLASSES = {
    "teal": "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-100",
    "violet": "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-100",
    "amber": "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100",
    "rose": "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-100",
    "sky": "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100",
    "lime": "bg-lime-100 text-lime-800 dark:bg-lime-900 dark:text-lime-100",
    "orange": "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100",
    "fuchsia": "bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900 dark:text-fuchsia-100",
}


@register.simple_tag
def member_color(color: str) -> str:
    """Clases de color de un miembro: {% member_color membership.color %}."""
    return MEMBER_COLOR_CLASSES.get(color, MEMBER_COLOR_CLASSES["teal"])


@register.filter
def euros(cents):
    """Muestra un importe en céntimos: {{ item.estimated_price_cents|euros }} → "12,50 €"."""
    return format_euros(cents)


@register.filter
def get_item(mapping, key):
    """Lee una clave de un diccionario: {{ colores|get_item:user.pk }}."""
    return mapping.get(key) if hasattr(mapping, "get") else None


# Versión intensa del color (puntos y barras).
MEMBER_DOT_CLASSES = {
    "teal": "bg-teal-500",
    "violet": "bg-violet-500",
    "amber": "bg-amber-500",
    "rose": "bg-rose-500",
    "sky": "bg-sky-500",
    "lime": "bg-lime-500",
    "orange": "bg-orange-500",
    "fuchsia": "bg-fuchsia-500",
}


@register.simple_tag
def member_dot(color: str) -> str:
    """Color intenso para puntos y barras: {% member_dot categoria.color %}."""
    return MEMBER_DOT_CLASSES.get(color, MEMBER_DOT_CLASSES["teal"])
