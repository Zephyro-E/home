"""Leer y escribir ingredientes en texto: "200 g de harina", "1/2 cebolla", "sal".

Así se escriben rápido (una línea por ingrediente) y se pueden escalar por raciones.
"""

import re
from decimal import Decimal, InvalidOperation

from django.utils.formats import number_format

# Unidades reconocidas (en minúsculas; se conservan tal como se escribieron).
_UNITS_TEXT = """
    g gr grs gramo gramos kg kilo kilos mg ml cl dl l litro litros cucharada cucharadas cda
    cdas cucharadita cucharaditas cdta cdtas taza tazas vaso vasos pizca pizcas puñado
    puñados chorro chorrito diente dientes lata latas sobre sobres rodaja rodajas loncha
    lonchas unidad unidades ud uds paquete paquetes bote botes hoja hojas rama ramas tbsp
    tsp cup cups oz lb
"""
UNITS = set(_UNITS_TEXT.split())
FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅛": "1/8"}
NUMBER = re.compile(r"^(\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)\s*")


def _to_decimal(text: str) -> Decimal | None:
    text = text.strip().replace(",", ".")
    try:
        if " " in text:  # "1 1/2"
            whole, frac = text.split(None, 1)
            return Decimal(whole) + _to_decimal(frac)
        if "/" in text:
            num, den = text.split("/", 1)
            return (Decimal(num) / Decimal(den)).quantize(Decimal("0.001"))
        return Decimal(text)
    except (InvalidOperation, ZeroDivisionError):
        return None


def parse_line(line: str) -> dict | None:
    """Convierte una línea en {quantity, unit, name}. Devuelve None si está vacía."""
    line = " ".join(line.strip().lstrip("-•*").split())
    if not line:
        return None
    for symbol, text in FRACTIONS.items():
        line = line.replace(symbol, f" {text} ").strip()
    line = " ".join(line.split())
    quantity, unit, rest = None, "", line
    match = NUMBER.match(rest)
    if match:
        quantity = _to_decimal(match.group(1))
        rest = rest[match.end() :]
        first, _sep, after = rest.partition(" ")
        if first.lower().rstrip(".") in UNITS and after:
            unit, rest = first, after
        if rest.lower().startswith("de "):
            rest = rest[3:]
    return {"quantity": quantity, "unit": unit, "name": rest.strip()[:150] or line[:150]}


def parse_text(text: str) -> list[dict]:
    return [item for item in (parse_line(line) for line in (text or "").splitlines()) if item]


def format_quantity(value: Decimal | None) -> str:
    """1.500 → "1,5"; 2.000 → "2"; 0.333 → "0,33" (con el separador del idioma)."""
    if value is None:
        return ""
    value = value.quantize(Decimal("0.01")).normalize()
    if value == value.to_integral():
        return str(int(value))
    places = max(0, -value.as_tuple().exponent)
    return number_format(value, places)


def to_line(quantity, unit: str, name: str) -> str:
    """Lo contrario de parse_line, para editar y para la lista de la compra."""
    parts = [format_quantity(quantity), unit, name]
    return " ".join(p for p in parts if p)


def scale(quantity: Decimal | None, factor: Decimal) -> Decimal | None:
    return None if quantity is None else quantity * factor
