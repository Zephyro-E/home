"""Lógica de finanzas: cuentas, categorías, movimientos, saldos y resumen mensual.

Privacidad: un movimiento es común si toca alguna cuenta común (así el saldo de esa
cuenta cuadra para todos) y personal si solo toca cuentas personales. Para crear o
editar un movimiento hay que poder usar todas las cuentas que toca.
"""

from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.utils.translation import gettext as _

from apps.core.models import Visibility

from .models import DEFAULT_CATEGORIES, Account, Category, Transaction

# --- Cuentas ------------------------------------------------------------------------------


def accounts_for(user, household, include_archived=True):
    qs = Account.objects.visible_to(user, household).select_related("owner")
    return qs if include_archived else qs.filter(is_archived=False)


def create_account(household, user, **data) -> Account:
    data["name"] = " ".join((data.get("name") or "").split())
    if not data["name"]:
        raise ValidationError(_("Escribe el nombre de la cuenta."))
    return Account.objects.create(household=household, owner=user, **data)


def update_account(account: Account, user, **data) -> Account:
    if not account.can_edit(user):
        raise PermissionDenied
    data.pop("visibility", None)  # cambiar la privacidad descuadraría movimientos ya hechos
    data["name"] = " ".join((data.get("name") or account.name).split())
    for name, value in data.items():
        setattr(account, name, value)
    account.save()
    return account


def set_archived(account: Account, user, archived: bool) -> Account:
    if not account.can_edit(user):
        raise PermissionDenied
    account.is_archived = archived
    account.save(update_fields=["is_archived", "updated_at"])
    return account


def delete_account(account: Account, user, membership) -> None:
    """Solo se borra una cuenta sin movimientos; si tiene, se archiva."""
    if not account.can_delete(user, membership):
        raise PermissionDenied
    try:
        account.delete()
    except ProtectedError as error:
        raise ValidationError(
            _("La cuenta tiene movimientos: archívala en lugar de borrarla.")
        ) from error


def balances(accounts) -> dict[int, int]:
    """Saldo actual (céntimos) de cada cuenta: inicial + ingresos − gastos ± transferencias.

    Se calcula con todos los movimientos de la cuenta, no solo los visibles: los de una
    cuenta común son siempre comunes, y los de una personal solo los ve su dueño.
    """
    ids = [a.pk for a in accounts]
    result = {a.pk: a.initial_balance_cents for a in accounts}
    out = (
        Transaction.objects.filter(account_id__in=ids)
        .values("account_id", "kind")
        .annotate(total=Sum("amount_cents"))
    )
    for row in out:
        sign = 1 if row["kind"] == Transaction.Kind.INCOME else -1
        result[row["account_id"]] += sign * row["total"]
    incoming = (
        Transaction.objects.filter(to_account_id__in=ids, kind=Transaction.Kind.TRANSFER)
        .values("to_account_id")
        .annotate(total=Sum("amount_cents"))
    )
    for row in incoming:
        result[row["to_account_id"]] += row["total"]
    return result


# --- Categorías ---------------------------------------------------------------------------


def ensure_default_categories(household, user) -> None:
    if Category.objects.filter(household=household).exists():
        return
    for kind, items in DEFAULT_CATEGORIES.items():
        for name, color in items:
            Category.objects.create(
                household=household, owner=user, kind=kind, name=str(name), color=color
            )


def categories_for(user, household, kind=None):
    ensure_default_categories(household, user)
    qs = Category.objects.visible_to(user, household)
    return qs.filter(kind=kind) if kind else qs


def create_category(household, user, name: str, kind: str, color: str) -> Category:
    name = " ".join((name or "").split())
    if not name:
        raise ValidationError(_("Escribe el nombre de la categoría."))
    if kind not in Category.Kind.values:
        raise ValidationError(_("Tipo no válido."))
    if Category.objects.filter(household=household, kind=kind, name__iexact=name).exists():
        raise ValidationError(_("Ya existe una categoría con ese nombre."))
    return Category.objects.create(
        household=household, owner=user, name=name[:60], kind=kind, color=color
    )


def delete_category(category: Category) -> None:
    """Cualquier miembro (son comunes). Sus movimientos quedan "sin categoría"."""
    category.delete()


# --- Movimientos --------------------------------------------------------------------------


def transactions_for(user, household):
    return Transaction.objects.visible_to(user, household).select_related(
        "account__owner", "to_account__owner", "category", "owner"
    )


def _prepare(household, user, data) -> dict:
    kind = data.get("kind")
    if kind not in Transaction.Kind.values:
        raise ValidationError(_("Tipo no válido."))
    amount = data.get("amount_cents")
    if not amount or amount <= 0:
        raise ValidationError(_("El importe debe ser mayor que cero."))
    account, to_account = data.get("account"), data.get("to_account")
    for acc in (account, to_account):
        if acc is None:
            continue
        if acc.household_id != household.pk or not acc.usable_by(user):
            raise ValidationError(_("No puedes usar esa cuenta."))
    if account is None:
        raise ValidationError(_("Elige una cuenta."))
    category = data.get("category")
    if kind == Transaction.Kind.TRANSFER:
        if to_account is None or to_account.pk == account.pk:
            raise ValidationError(_("Elige una cuenta de destino distinta."))
        data["category"] = None
    else:
        data["to_account"] = None
        if category is not None and (
            category.household_id != household.pk or category.kind != kind
        ):
            raise ValidationError(_("La categoría no corresponde a este tipo de movimiento."))
    shared = account.visibility == Visibility.SHARED or (
        to_account is not None and to_account.visibility == Visibility.SHARED
    )
    data["visibility"] = Visibility.SHARED if shared else Visibility.PRIVATE
    data["description"] = " ".join((data.get("description") or "").split())[:200]
    return data


def create_transaction(household, user, **data) -> Transaction:
    data = _prepare(household, user, data)
    return Transaction.objects.create(household=household, owner=user, **data)


def update_transaction(tx: Transaction, user, **data) -> Transaction:
    if not tx.can_edit(user):
        raise PermissionDenied
    data = _prepare(tx.household, user, data)
    for name, value in data.items():
        setattr(tx, name, value)
    tx.save()
    return tx


def delete_transaction(tx: Transaction, user, membership) -> None:
    if not tx.can_delete(user, membership):
        raise PermissionDenied
    tx.delete()


def month_range(month: date) -> tuple[date, date]:
    first = month.replace(day=1)
    following = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return first, following


def filter_scope(qs, user, scope: str):
    """'comun' = solo lo común; 'mio' = solo lo personal propio; otro = todo lo visible."""
    if scope == "comun":
        return qs.filter(visibility=Visibility.SHARED)
    if scope == "mio":
        return qs.filter(visibility=Visibility.PRIVATE, owner=user)
    return qs


def month_summary(user, household, month: date, scope: str = "") -> dict:
    """Ingresos, gastos y saldo del mes (sin transferencias) y gastos por categoría."""
    first, following = month_range(month)
    qs = filter_scope(transactions_for(user, household), user, scope).filter(
        date__gte=first, date__lt=following
    )
    totals = qs.aggregate(
        income=Sum("amount_cents", filter=Q(kind=Transaction.Kind.INCOME), default=0),
        expense=Sum("amount_cents", filter=Q(kind=Transaction.Kind.EXPENSE), default=0),
    )
    rows = (
        qs.filter(kind=Transaction.Kind.EXPENSE)
        .values("category_id", "category__name", "category__color")
        .annotate(total=Sum("amount_cents"))
        .order_by("-total")
    )
    expense = totals["expense"]
    by_category = [
        {
            "name": row["category__name"] or _("Sin categoría"),
            "color": row["category__color"] or "teal",
            "total": row["total"],
            "percent": round(row["total"] * 100 / expense) if expense else 0,
        }
        for row in rows
    ]
    return {
        "income": totals["income"],
        "expense": expense,
        "net": totals["income"] - expense,
        "by_category": by_category,
        "count": qs.count(),
    }
