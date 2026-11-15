"""Recurrencias en formato RRULE (RFC 5545, ADR-012), compartidas por eventos y tareas.

La interfaz ofrece opciones sencillas (cada día / semana / mes / año, cada N, hasta una
fecha) y se guardan como texto RRULE sin DTSTART, p. ej. "FREQ=WEEKLY;INTERVAL=2".
Las repeticiones se calculan siempre en hora local (sin zona), de modo que un evento de
las 18:00 sigue a las 18:00 tras el cambio de horario.
"""

import re
from contextlib import suppress
from datetime import date, datetime, time

from dateutil.rrule import rrulestr
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

FREQUENCIES = [
    ("", gettext_lazy("No se repite")),
    ("DAILY", gettext_lazy("Cada día")),
    ("WEEKLY", gettext_lazy("Cada semana")),
    ("MONTHLY", gettext_lazy("Cada mes")),
    ("YEARLY", gettext_lazy("Cada año")),
]
_FREQ_VALUES = {f for f, _label in FREQUENCIES if f}
_PART = re.compile(r"^(FREQ|INTERVAL|UNTIL)=([A-Z0-9]+)$")


def build_rule(freq: str, interval: int = 1, until: date | None = None) -> str:
    """Construye la regla. Devuelve "" si no se repite."""
    if freq not in _FREQ_VALUES:
        return ""
    parts = [f"FREQ={freq}"]
    if interval and interval > 1:
        parts.append(f"INTERVAL={int(interval)}")
    if until:
        parts.append(f"UNTIL={until:%Y%m%d}T235959")
    return ";".join(parts)


def parse_rule(rule: str) -> dict:
    """Lo contrario de build_rule: {"freq", "interval", "until"}. Ignora lo desconocido."""
    data = {"freq": "", "interval": 1, "until": None}
    for part in (rule or "").split(";"):
        match = _PART.match(part.strip())
        if not match:
            continue
        key, value = match.groups()
        if key == "FREQ" and value in _FREQ_VALUES:
            data["freq"] = value
        elif key == "INTERVAL" and value.isdigit():
            data["interval"] = max(1, int(value))
        elif key == "UNTIL":
            with suppress(ValueError):
                data["until"] = datetime.strptime(value[:8], "%Y%m%d").date()
    return data


def is_valid(rule: str) -> bool:
    try:
        rrulestr(rule, dtstart=datetime(2000, 1, 1))
    except (ValueError, TypeError):
        return False
    return True


def between(rule: str, dtstart: datetime, start: datetime, end: datetime) -> list[datetime]:
    """Repeticiones (fechas-hora locales, sin zona) entre start y end, ambos incluidos."""
    return list(rrulestr(rule, dtstart=dtstart).between(start, end, inc=True))


def next_date(rule: str, current: date) -> date | None:
    """Siguiente fecha de la serie después de `current` (para tareas recurrentes)."""
    dtstart = datetime.combine(current, time())
    following = rrulestr(rule, dtstart=dtstart).after(dtstart, inc=False)
    return following.date() if following else None


def describe(rule: str) -> str:
    """Texto legible: "Cada 2 semanas, hasta el 01/03/2027"."""
    data = parse_rule(rule)
    if not data["freq"]:
        return ""
    n = data["interval"]
    if n == 1:
        text = str(dict(FREQUENCIES)[data["freq"]])
    else:
        units = {
            "DAILY": _("Cada %(n)s días"),
            "WEEKLY": _("Cada %(n)s semanas"),
            "MONTHLY": _("Cada %(n)s meses"),
            "YEARLY": _("Cada %(n)s años"),
        }
        text = units[data["freq"]] % {"n": n}
    if data["until"]:
        text += _(", hasta el %(date)s") % {"date": data["until"].strftime("%d/%m/%Y")}
    return text
