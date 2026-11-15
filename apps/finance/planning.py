"""Presupuestos, metas de ahorro y datos para los gráficos."""

from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.utils.translation import gettext as _

from apps.core.models import Visibility

from . import services
from .models import Budget, Category, SavingsGoal, Transaction

# --- Presupuestos -------------------------------------------------------------------------


def budgets_for(user, household):
    return Budget.objects.visible_to(user, household).select_related("category")


def set_budget(household, user, category: Category, amount_cents: int) -> Budget | None:
    """Crea o cambia el presupuesto mensual de una categoría de gastos. 0 = quitarlo."""
    if category.household_id != household.pk or category.kind != Category.Kind.EXPENSE:
        raise ValidationError(_("Elige una categoría de gastos."))
    if amount_cents < 0:
        raise ValidationError(_("El importe no puede ser negativo."))
    if amount_cents == 0:
        Budget.objects.filter(category=category).delete()
        return None
    budget, _created = Budget.objects.update_or_create(
        category=category,
        defaults={"household": household, "owner": user, "amount_cents": amount_cents},
    )
    return budget


def budget_progress(user, household, month: date) -> list[dict]:
    """Gasto del mes frente al presupuesto. Cuenta lo común (los presupuestos son del hogar)."""
    first, following = services.month_range(month)
    spent = dict(
        Transaction.objects.filter(
            household=household,
            visibility=Visibility.SHARED,
            kind=Transaction.Kind.EXPENSE,
            date__gte=first,
            date__lt=following,
        )
        .values_list("category_id")
        .annotate(total=Sum("amount_cents"))
    )
    rows = []
    for budget in budgets_for(user, household):
        used = spent.get(budget.category_id, 0)
        percent = round(used * 100 / budget.amount_cents) if budget.amount_cents else 0
        rows.append(
            {
                "budget": budget,
                "category": budget.category,
                "spent": used,
                "left": budget.amount_cents - used,
                "percent": percent,
                "bar": min(percent, 100),
                "state": "over" if percent > 100 else "warn" if percent >= 80 else "ok",
            }
        )
    return rows


# --- Metas de ahorro ----------------------------------------------------------------------


def goals_for(user, household):
    return SavingsGoal.objects.visible_to(user, household).select_related("account")


def goal_progress(goals) -> list[dict]:
    accounts = [g.account for g in goals if g.account_id]
    balances = services.balances(accounts) if accounts else {}
    rows = []
    for goal in goals:
        saved = balances.get(goal.account_id, 0) if goal.account_id else goal.saved_cents
        percent = round(saved * 100 / goal.target_cents) if goal.target_cents else 0
        rows.append(
            {
                "goal": goal,
                "saved": saved,
                "left": max(goal.target_cents - saved, 0),
                "percent": percent,
                "bar": max(min(percent, 100), 0),
            }
        )
    return rows


def _check_goal_account(household, user, account, visibility):
    if account is None:
        return
    if account.household_id != household.pk or not account.usable_by(user):
        raise ValidationError(_("No puedes usar esa cuenta."))
    if visibility == Visibility.SHARED and account.visibility == Visibility.PRIVATE:
        raise ValidationError(_("Una meta común no puede vincularse a una cuenta personal."))


def create_goal(household, user, **data) -> SavingsGoal:
    data["name"] = " ".join((data.get("name") or "").split())
    if not data["name"]:
        raise ValidationError(_("Escribe el nombre de la meta."))
    if not data.get("target_cents"):
        raise ValidationError(_("Indica cuánto quieres ahorrar."))
    _check_goal_account(household, user, data.get("account"), data.get("visibility", "shared"))
    return SavingsGoal.objects.create(household=household, owner=user, **data)


def update_goal(goal: SavingsGoal, user, **data) -> SavingsGoal:
    if not goal.can_edit(user):
        raise PermissionDenied
    data.pop("visibility", None)
    _check_goal_account(goal.household, user, data.get("account"), goal.visibility)
    for name, value in data.items():
        setattr(goal, name, value)
    goal.save()
    return goal


def contribute(goal: SavingsGoal, user, amount_cents: int) -> SavingsGoal:
    """Apunta una aportación (o retirada, si es negativa) en una meta sin cuenta."""
    if not goal.can_edit(user):
        raise PermissionDenied
    if goal.account_id:
        raise ValidationError(
            _("Esta meta sigue el saldo de su cuenta: apunta allí los movimientos.")
        )
    goal.saved_cents += amount_cents
    goal.save(update_fields=["saved_cents", "updated_at"])
    return goal


def delete_goal(goal: SavingsGoal, user, membership) -> None:
    if not goal.can_delete(user, membership):
        raise PermissionDenied
    goal.delete()


# --- Gráficos -----------------------------------------------------------------------------


def monthly_totals(user, household, month: date, scope: str = "", months: int = 12) -> list[dict]:
    """Ingresos y gastos de los últimos `months` meses hasta `month` (incluido)."""
    first_month = month.replace(day=1)
    for _i in range(months - 1):
        first_month = date(
            first_month.year - (first_month.month == 1), (first_month.month - 2) % 12 + 1, 1
        )
    _first, following = services.month_range(month)
    qs = services.filter_scope(services.transactions_for(user, household), user, scope).filter(
        date__gte=first_month, date__lt=following
    )
    rows = (
        qs.annotate(m=TruncMonth("date"))
        .values("m")
        .annotate(
            income=Sum("amount_cents", filter=Q(kind=Transaction.Kind.INCOME), default=0),
            expense=Sum("amount_cents", filter=Q(kind=Transaction.Kind.EXPENSE), default=0),
        )
    )
    by_month = {r["m"]: r for r in rows}
    result, current = [], first_month
    for _i in range(months):
        r = by_month.get(current, {})
        result.append(
            {"month": current, "income": r.get("income", 0), "expense": r.get("expense", 0)}
        )
        current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
    top = max([max(r["income"], r["expense"]) for r in result] + [1])
    for r in result:
        r["income_pct"] = round(r["income"] * 100 / top)
        r["expense_pct"] = round(r["expense"] * 100 / top)
    return result
