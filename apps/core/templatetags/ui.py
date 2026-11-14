"""Etiquetas de plantilla reutilizables para la interfaz."""

import re
from functools import lru_cache

from django import template
from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe

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
