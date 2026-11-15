"""Gastos compartidos: reparto entre miembros, saldos y pagos para saldarlos.

Un gasto se reparte cuando alguien lo paga con una cuenta personal (lo que sale de una
cuenta común ya es dinero de todos). Quien paga adelanta el dinero; cada persona debe
su parte. Los pagos entre miembros (Settlement) compensan esas deudas.

Repartos en puntos básicos (10 000 = 100 %) y céntimos enteros; el céntimo que sobra al
redondear se asigna de forma determinista (ADR-007).
"""

from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.translation import gettext as _

from apps.core.models import Membership, Visibility

from .models import Settlement, Transaction, TransactionSplit

FULL = 10_000


def allocate(amount_cents: int, shares: list[tuple[object, int]]) -> list[tuple[object, int]]:
    """Reparte un importe según porcentajes (bp). La suma de partes es exactamente el total.

    Cada parte se redondea hacia abajo y los céntimos sobrantes van, de uno en uno, a quien
    tenga mayor resto (a igualdad, en el orden recibido).
    """
    total_bp = sum(bp for _key, bp in shares)
    if total_bp != FULL:
        raise ValidationError(_("El reparto debe sumar el 100 %."))
    parts = []
    for index, (key, bp) in enumerate(shares):
        exact = amount_cents * bp
        parts.append([key, exact // FULL, exact % FULL, index])
    leftover = amount_cents - sum(p[1] for p in parts)
    for part in sorted(parts, key=lambda p: (-p[2], p[3]))[:leftover]:
        part[1] += 1
    return [(key, cents) for key, cents, _rest, _i in parts]


def default_shares(household) -> list[tuple[object, int]]:
    """Reparto por defecto del hogar, normalizado para que sume el 100 %."""
    memberships = list(
        Membership.objects.filter(household=household).select_related("user").order_by("joined_at")
    )
    if not memberships:
        return []
    total = sum(m.default_share_bp for m in memberships)
    if total <= 0:  # nadie tiene parte: a partes iguales
        return [(m.user, b) for m, b in zip(memberships, _equal(len(memberships)), strict=True)]
    raw = [(m.user, m.default_share_bp * FULL // total) for m in memberships]
    # Ajusta el redondeo en la primera persona para sumar exactamente 10 000.
    diff = FULL - sum(bp for _u, bp in raw)
    raw[0] = (raw[0][0], raw[0][1] + diff)
    return raw


def _equal(n: int) -> list[int]:
    base, extra = divmod(FULL, n)
    return [base + (1 if i < extra else 0) for i in range(n)]


def set_default_shares(household, user_membership, shares: dict[int, int]) -> None:
    """Guarda el reparto por defecto (solo administración). `shares`: {user_id: bp}."""
    if not user_membership.is_admin:
        raise PermissionDenied
    memberships = list(Membership.objects.filter(household=household))
    if set(shares) != {m.user_id for m in memberships}:
        raise ValidationError(_("Indica el reparto de todos los miembros."))
    if sum(shares.values()) != FULL:
        raise ValidationError(_("El reparto debe sumar el 100 %."))
    for m in memberships:
        m.default_share_bp = shares[m.user_id]
        m.save(update_fields=["default_share_bp"])


def validate_split(household, account, shares) -> None:
    if account.visibility != Visibility.PRIVATE:
        # Lo que sale de una cuenta común ya es dinero de todos: no genera deudas.
        raise ValidationError(_("Solo se reparten gastos pagados con una cuenta personal."))
    member_ids = set(
        Membership.objects.filter(household=household).values_list("user_id", flat=True)
    )
    if not shares or any(u.pk not in member_ids for u, _bp in shares):
        raise ValidationError(_("El reparto solo puede incluir miembros del hogar."))
    if any(bp < 0 for _u, bp in shares) or sum(bp for _u, bp in shares) != FULL:
        raise ValidationError(_("El reparto debe sumar el 100 %."))


def save_splits(tx: Transaction, shares) -> None:
    tx.splits.all().delete()
    if not tx.is_split:
        return
    shares = [(u, bp) for u, bp in shares if bp > 0]
    for user, cents in allocate(tx.amount_cents, shares):
        bp = next(b for u, b in shares if u.pk == user.pk)
        TransactionSplit.objects.create(transaction=tx, user=user, share_bp=bp, amount_cents=cents)


# --- Saldos -------------------------------------------------------------------------------


def balances(household) -> dict[int, int]:
    """Saldo de cada persona en céntimos: positivo = le deben; negativo = debe."""
    net: dict[int, int] = defaultdict(int)
    split_txs = Transaction.objects.filter(household=household, is_split=True).select_related(
        "account"
    )
    for tx in split_txs.prefetch_related("splits"):
        net[tx.account.owner_id] += tx.amount_cents
        for split in tx.splits.all():
            net[split.user_id] -= split.amount_cents
    for s in Settlement.objects.filter(household=household):
        net[s.from_user_id] += s.amount_cents
        net[s.to_user_id] -= s.amount_cents
    return {uid: cents for uid, cents in net.items() if cents}


def suggested_payments(net: dict[int, int]) -> list[tuple[int, int, int]]:
    """Pagos mínimos para dejar todos los saldos a cero: [(de, a, céntimos)]."""
    debtors = sorted(((-c, u) for u, c in net.items() if c < 0), reverse=True)
    creditors = sorted(((c, u) for u, c in net.items() if c > 0), reverse=True)
    debtors = [[c, u] for c, u in debtors]
    creditors = [[c, u] for c, u in creditors]
    payments = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][0], creditors[j][0])
        payments.append((debtors[i][1], creditors[j][1], amount))
        debtors[i][0] -= amount
        creditors[j][0] -= amount
        if debtors[i][0] == 0:
            i += 1
        if creditors[j][0] == 0:
            j += 1
    return payments


# --- Pagos entre miembros -----------------------------------------------------------------


def settlements_for(user, household):
    return Settlement.objects.visible_to(user, household).select_related("from_user", "to_user")


def create_settlement(
    household, user, from_user, to_user, amount_cents, date, note=""
) -> Settlement:
    member_ids = set(
        Membership.objects.filter(household=household).values_list("user_id", flat=True)
    )
    if from_user.pk not in member_ids or to_user.pk not in member_ids:
        raise ValidationError(_("Las dos personas deben ser miembros del hogar."))
    if from_user.pk == to_user.pk:
        raise ValidationError(_("Elige dos personas distintas."))
    if amount_cents <= 0:
        raise ValidationError(_("El importe debe ser mayor que cero."))
    return Settlement.objects.create(
        household=household,
        owner=user,
        from_user=from_user,
        to_user=to_user,
        amount_cents=amount_cents,
        date=date,
        note=" ".join((note or "").split())[:200],
    )


def delete_settlement(settlement: Settlement, user, membership) -> None:
    """Lo borra quien lo apuntó, cualquiera de las dos personas o la administración."""
    allowed = user.pk in {settlement.owner_id, settlement.from_user_id, settlement.to_user_id}
    if not (allowed or membership.is_admin):
        raise PermissionDenied
    settlement.delete()


def split_expenses(user, household, first, following):
    """Gastos compartidos del periodo (los ve todo el hogar)."""
    return (
        Transaction.objects.visible_to(user, household)
        .filter(is_split=True, date__gte=first, date__lt=following)
        .select_related("account__owner", "category")
        .prefetch_related("splits__user")
    )
