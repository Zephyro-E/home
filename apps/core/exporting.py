"""Exportar los datos del hogar a JSON (todo) o CSV (por módulo).

Solo se exporta lo que la persona puede ver (visible_to, ADR-005): lo común del hogar y
lo personal propio. Los CSV usan ";" y coma decimal, con BOM, para que Excel en español
los abra bien a la primera.
"""

import csv
import io
import json

from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def _amount(cents):
    """Importe para hoja de cálculo: 1250 → "12,50" (vacío si no hay)."""
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100},{abs(cents) % 100:02d}"


def _visibility(obj):
    return "personal" if obj.visibility == "private" else "común"


def _grocery(user, household):
    from apps.shopping.services import grocery_for

    headers = ["producto", "cantidad", "comprado", "añadido por", "creado"]
    rows = [
        [g.name, g.quantity, "sí" if g.is_checked else "no", str(g.owner), g.created_at]
        for g in grocery_for(user, household)
    ]
    return headers, rows


def _wishes(user, household):
    from apps.shopping.services import wishes_for

    headers = ["nombre", "visibilidad", "estado", "prioridad", "precio", "enlace", "de", "creado"]
    rows = [
        [
            w.name,
            _visibility(w),
            w.get_status_display(),
            w.get_priority_display(),
            _amount(w.estimated_price_cents),
            w.url,
            str(w.owner),
            w.created_at,
        ]
        for w in wishes_for(user, household)
    ]
    return headers, rows


def _tasks(user, household):
    from apps.tasks.services import tasks_for

    headers = [
        "título",
        "visibilidad",
        "estado",
        "responsable",
        "fecha límite",
        "prioridad",
        "repetición",
        "etiquetas",
        "descripción",
    ]
    rows = [
        [
            t.title,
            _visibility(t),
            t.get_status_display(),
            str(t.assignee or ""),
            t.due_date or "",
            t.get_priority_display(),
            t.recurrence_text,
            ", ".join(lb.name for lb in t.labels.all()),
            t.description,
        ]
        for t in tasks_for(user, household).prefetch_related("labels")
    ]
    return headers, rows


def _events(user, household):
    from apps.events.services import events_for

    headers = [
        "título",
        "visibilidad",
        "tipo",
        "todo el día",
        "inicio",
        "fin",
        "lugar",
        "repetición",
    ]
    rows = []
    for e in events_for(user, household):
        if e.all_day:
            start, end = e.start_date, e.end_date
        else:
            start = timezone.localtime(e.starts_at).strftime("%Y-%m-%d %H:%M")
            end = timezone.localtime(e.ends_at).strftime("%Y-%m-%d %H:%M")
        rows.append(
            [
                e.title,
                _visibility(e),
                e.get_kind_display(),
                "sí" if e.all_day else "no",
                start,
                end,
                e.location,
                e.recurrence_text,
            ]
        )
    return headers, rows


def _media(user, household):
    from apps.media.services import titles_for

    headers = ["título", "visibilidad", "tipo", "estado", "año", "género", "dónde verla"]
    rows = [
        [
            t.title,
            _visibility(t),
            t.get_kind_display(),
            t.get_status_display(),
            t.year or "",
            t.genre,
            t.platform,
        ]
        for t in titles_for(user, household)
    ]
    return headers, rows


def _places(user, household):
    from apps.places.services import places_for

    headers = ["nombre", "visibilidad", "categoría", "estado", "zona", "visitado el", "enlace"]
    rows = [
        [
            p.name,
            _visibility(p),
            p.get_category_display(),
            p.get_status_display(),
            p.location,
            p.visited_on or "",
            p.url,
        ]
        for p in places_for(user, household)
    ]
    return headers, rows


def _recipes(user, household):
    from apps.recipes.services import ingredients_text, recipes_for

    headers = ["título", "visibilidad", "tipo", "raciones", "ingredientes", "pasos", "etiquetas"]
    rows = [
        [
            r.title,
            _visibility(r),
            r.get_course_display(),
            r.servings,
            ingredients_text(r),
            r.instructions,
            r.tags,
        ]
        for r in recipes_for(user, household).prefetch_related("ingredients")
    ]
    return headers, rows


def _accounts(user, household):
    from apps.finance.services import accounts_for, balances

    accounts = list(accounts_for(user, household))
    saldos = balances(accounts)
    headers = ["cuenta", "visibilidad", "tipo", "saldo inicial", "saldo actual", "archivada"]
    rows = [
        [
            a.name,
            _visibility(a),
            a.get_kind_display(),
            _amount(a.initial_balance_cents),
            _amount(saldos[a.pk]),
            "sí" if a.is_archived else "no",
        ]
        for a in accounts
    ]
    return headers, rows


def _transactions(user, household):
    from apps.finance.services import transactions_for
    from apps.finance.templatetags.finance import account_label

    headers = [
        "fecha",
        "tipo",
        "importe",
        "concepto",
        "categoría",
        "cuenta",
        "cuenta destino",
        "compartido",
        "visibilidad",
    ]
    rows = [
        [
            t.date,
            t.get_kind_display(),
            _amount(t.amount_cents),
            t.description,
            t.category.name if t.category else "",
            account_label(t.account, user),
            account_label(t.to_account, user) if t.to_account_id else "",
            "sí" if t.is_split else "no",
            _visibility(t),
        ]
        for t in transactions_for(user, household)
    ]
    return headers, rows


# (clave, nombre visible, función). La clave se usa en la URL del CSV.
SECTIONS = [
    ("lista-compra", _("Lista de la compra"), _grocery),
    ("deseos", _("Deseos"), _wishes),
    ("tareas", _("Tareas"), _tasks),
    ("eventos", _("Calendario"), _events),
    ("peliculas", _("Películas y series"), _media),
    ("sitios", _("Sitios"), _places),
    ("recetas", _("Recetas"), _recipes),
    ("cuentas", _("Cuentas"), _accounts),
    ("movimientos", _("Movimientos"), _transactions),
]
SECTION_KEYS = {key for key, _label, _builder in SECTIONS}


def _cell(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat") and hasattr(value, "hour"):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def to_csv(user, household, key: str) -> str:
    builder = next(b for k, _label, b in SECTIONS if k == key)
    headers, rows = builder(user, household)
    out = io.StringIO()
    out.write("﻿")  # BOM: Excel detecta UTF-8 (tildes y ñ)
    writer = csv.writer(out, delimiter=";")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return out.getvalue()


def to_json(user, household) -> str:
    data = {
        "hogar": household.name,
        "exportado": timezone.localtime().isoformat(timespec="seconds"),
        "por": str(user),
        "nota": "Solo incluye lo que esta persona puede ver: lo común y lo personal propio.",
    }
    for key, _label, builder in SECTIONS:
        headers, rows = builder(user, household)
        data[key] = [dict(zip(headers, (_cell(v) for v in row), strict=True)) for row in rows]
    return json.dumps(data, ensure_ascii=False, indent=2)
