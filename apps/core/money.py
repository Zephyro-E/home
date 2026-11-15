"""Importes en céntimos enteros (ADR-007): conversión desde texto y formato para mostrar."""

import re
from decimal import Decimal, InvalidOperation

from django.utils.formats import number_format

_AMOUNT = re.compile(r"^\d+(?:[.,]\d{1,2})?$")


def parse_euros(text: str) -> int | None:
    """Convierte "12", "12,5" o "12.50" en céntimos (1250). Devuelve None si no es válido.

    Se acepta coma o punto como separador decimal. No se aceptan separadores de miles
    ni importes negativos.
    """
    text = (text or "").strip().replace("€", "").strip()
    if not _AMOUNT.match(text):
        return None
    try:
        value = Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None
    return int((value * 100).to_integral_value())


def cents_to_input(cents: int | None) -> str:
    """Texto para un campo de formulario: 1250 → "12,50" (o "12.50" en inglés)."""
    if cents is None:
        return ""
    return number_format(Decimal(cents) / 100, 2)


def format_euros(cents: int | None) -> str:
    """Importe para mostrar: 1250 → "12,50 €"."""
    if cents is None:
        return ""
    return f"{number_format(Decimal(cents) / 100, 2, force_grouping=True)} €"
