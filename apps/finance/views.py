"""Vistas de finanzas. Los datos parten de visible_to; las reglas viven en services.py."""

from datetime import date
from itertools import groupby

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import HouseholdRequiredMixin
from apps.core.models import MEMBER_COLORS, Membership

from . import planning, services, sharing
from .forms import (
    AccountForm,
    BudgetForm,
    CategoryForm,
    ContributionForm,
    GoalForm,
    SettlementForm,
    TransactionForm,
)
from .models import Category, Transaction

SCOPES = {"comun", "mio"}
User = get_user_model()


def _month(text) -> date:
    today = timezone.localdate()
    try:
        year, month = (int(p) for p in (text or "").split("-"))
        if 1900 <= year <= 2200:
            return date(year, month, 1)
    except ValueError:
        pass
    return today.replace(day=1)


def _shift(month: date, n: int) -> date:
    m = month.month - 1 + n
    return date(month.year + m // 12, m % 12 + 1, 1)


class FinanceMixin(HouseholdRequiredMixin):
    def month_nav(self, month):
        return {
            "month": month,
            "prev_month": _shift(month, -1),
            "next_month": _shift(month, 1),
            "is_current_month": month == timezone.localdate().replace(day=1),
        }


class SummaryView(FinanceMixin, TemplateView):
    template_name = "finance/summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, household = self.request.user, self.request.household
        month = _month(self.request.GET.get("mes"))
        scope = self.request.GET.get("ver") if self.request.GET.get("ver") in SCOPES else ""
        accounts = list(services.accounts_for(user, household, include_archived=False))
        balances = services.balances(accounts)
        for account in accounts:
            account.balance = balances[account.pk]
        services.ensure_default_categories(household, user)
        recent = services.filter_scope(services.transactions_for(user, household), user, scope)
        context.update(self.month_nav(month))
        context.update(
            scope=scope,
            summary=services.month_summary(user, household, month, scope),
            chart=planning.monthly_totals(user, household, month, scope),
            budgets=planning.budget_progress(user, household, month),
            accounts=accounts,
            recent=list(recent[:8]),
        )
        return context


class TransactionListView(FinanceMixin, TemplateView):
    template_name = "finance/transactions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, household = self.request.user, self.request.household
        get = self.request.GET
        month = _month(get.get("mes"))
        first, following = services.month_range(month)
        qs = services.transactions_for(user, household).filter(date__gte=first, date__lt=following)
        scope = get.get("ver") if get.get("ver") in SCOPES else ""
        qs = services.filter_scope(qs, user, scope)
        account_id = get.get("cuenta", "")
        if account_id.isdigit():
            qs = qs.filter(Q(account_id=account_id) | Q(to_account_id=account_id))
        category_id = get.get("categoria", "")
        if category_id.isdigit():
            qs = qs.filter(category_id=category_id)
        kind = get.get("tipo") if get.get("tipo") in Transaction.Kind.values else ""
        if kind:
            qs = qs.filter(kind=kind)
        items = list(qs.order_by("-date", "-created_at"))
        context.update(self.month_nav(month))
        context.update(
            days=[(day, list(group)) for day, group in groupby(items, key=lambda t: t.date)],
            scope=scope,
            kind=kind,
            account_id=int(account_id) if account_id.isdigit() else None,
            category_id=int(category_id) if category_id.isdigit() else None,
            accounts=services.accounts_for(user, household),
            categories=services.categories_for(user, household),
            kinds=Transaction.Kind.choices,
            query=get.urlencode(),
        )
        return context


class TransactionMixin(FinanceMixin):
    def get_tx(self, pk):
        visible = services.transactions_for(self.request.user, self.request.household)
        return get_object_or_404(visible, pk=pk)

    def form(self, data=None, **kwargs):
        return TransactionForm(
            data, user=self.request.user, household=self.request.household, **kwargs
        )


class TransactionCreateView(TransactionMixin, View):
    template_name = "finance/transaction_form.html"

    def get(self, request):
        services.ensure_default_categories(request.household, request.user)
        initial = {}
        if request.GET.get("tipo") in Transaction.Kind.values:
            initial["kind"] = request.GET["tipo"]
        if request.GET.get("cuenta", "").isdigit():
            initial["account"] = int(request.GET["cuenta"])
        return render(request, self.template_name, {"form": self.form(initial=initial)})

    def post(self, request):
        form = self.form(request.POST)
        if form.is_valid():
            try:
                services.create_transaction(
                    request.household, request.user, **form.transaction_data()
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Movimiento guardado."))
                if request.POST.get("another"):
                    return redirect(request.path + f"?tipo={form.cleaned_data['kind']}")
                return redirect("finance:transactions")
        return render(request, self.template_name, {"form": form}, status=400)


class TransactionEditView(TransactionMixin, View):
    template_name = "finance/transaction_form.html"

    def get_editable(self, pk):
        tx = self.get_tx(pk)
        if not tx.can_edit(self.request.user):
            raise Http404
        return tx

    def get(self, request, pk):
        tx = self.get_editable(pk)
        context = {
            "form": self.form(instance=tx),
            "tx": tx,
            "can_delete": tx.can_delete(request.user, request.membership),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        tx = self.get_editable(pk)
        form = self.form(request.POST, instance=tx)
        if form.is_valid():
            try:
                services.update_transaction(tx, request.user, **form.transaction_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("finance:transactions")
        context = {
            "form": form,
            "tx": tx,
            "can_delete": tx.can_delete(request.user, request.membership),
        }
        return render(request, self.template_name, context, status=400)


class TransactionDeleteView(TransactionMixin, View):
    def post(self, request, pk):
        services.delete_transaction(self.get_tx(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        messages.success(request, _("Movimiento borrado."))
        return redirect("finance:transactions")


# --- Cuentas ------------------------------------------------------------------------------


class AccountListView(FinanceMixin, TemplateView):
    template_name = "finance/accounts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        accounts = list(services.accounts_for(self.request.user, self.request.household))
        balances = services.balances(accounts)
        for account in accounts:
            account.balance = balances[account.pk]
        context.update(
            active=[a for a in accounts if not a.is_archived],
            archived=[a for a in accounts if a.is_archived],
            total=sum(a.balance for a in accounts if not a.is_archived),
        )
        return context


class AccountMixin(FinanceMixin):
    def get_account(self, pk, editable=False):
        account = get_object_or_404(
            services.accounts_for(self.request.user, self.request.household), pk=pk
        )
        if editable and not account.can_edit(self.request.user):
            raise Http404
        return account


class AccountCreateView(AccountMixin, View):
    template_name = "finance/account_form.html"

    def get(self, request):
        return render(
            request, self.template_name, {"form": AccountForm(initial={"visibility": "shared"})}
        )

    def post(self, request):
        form = AccountForm(request.POST)
        if form.is_valid():
            try:
                services.create_account(request.household, request.user, **form.account_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cuenta creada."))
                return redirect("finance:accounts")
        return render(request, self.template_name, {"form": form}, status=400)


class AccountEditView(AccountMixin, View):
    template_name = "finance/account_form.html"

    def get(self, request, pk):
        account = self.get_account(pk, editable=True)
        context = {"form": AccountForm(instance=account), "account": account}
        return render(request, self.template_name, context)

    def post(self, request, pk):
        account = self.get_account(pk, editable=True)
        if "archive" in request.POST:
            services.set_archived(account, request.user, request.POST["archive"] == "1")
            return redirect("finance:accounts")
        if "delete" in request.POST:
            try:
                services.delete_account(account, request.user, request.membership)
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
                return redirect("finance:account_edit", pk=pk)
            messages.success(request, _("Cuenta borrada."))
            return redirect("finance:accounts")
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            services.update_account(account, request.user, **form.account_data())
            messages.success(request, _("Cambios guardados."))
            return redirect("finance:accounts")
        return render(request, self.template_name, {"form": form, "account": account}, status=400)


# --- Categorías ---------------------------------------------------------------------------


class CategoriesView(FinanceMixin, View):
    template_name = "finance/categories.html"

    def render_page(self, form, status=200):
        categories = services.categories_for(self.request.user, self.request.household)
        context = {
            "form": form,
            "expense": [c for c in categories if c.kind == Category.Kind.EXPENSE],
            "income": [c for c in categories if c.kind == Category.Kind.INCOME],
            "colors": MEMBER_COLORS,
        }
        return render(self.request, self.template_name, context, status=status)

    def get(self, request):
        return self.render_page(
            CategoryForm(initial={"kind": "expense", "color": MEMBER_COLORS[0]})
        )

    def post(self, request):
        form = CategoryForm(request.POST)
        if form.is_valid():
            try:
                d = form.cleaned_data
                services.create_category(
                    request.household, request.user, d["name"], d["kind"], d["color"]
                )
            except ValidationError as error:
                form.add_error("name", error)
            else:
                messages.success(request, _("Categoría creada."))
                return redirect("finance:categories")
        return self.render_page(form, status=400)


class CategoryDeleteView(FinanceMixin, View):
    def post(self, request, pk):
        category = get_object_or_404(
            Category.objects.visible_to(request.user, request.household), pk=pk
        )
        services.delete_category(category)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect("finance:categories")


# --- Gastos compartidos -------------------------------------------------------------------


def _members(household):
    return {
        m.user_id: m for m in Membership.objects.filter(household=household).select_related("user")
    }


class SharedView(FinanceMixin, TemplateView):
    template_name = "finance/shared.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, household = self.request.user, self.request.household
        month = _month(self.request.GET.get("mes"))
        first, following = services.month_range(month)
        members = _members(household)
        net = sharing.balances(household)
        users = {uid: m.user for uid, m in members.items()}
        missing = set(net) - set(users)  # antiguos miembros con saldo pendiente
        if missing:
            users.update({u.pk: u for u in User.objects.filter(pk__in=missing)})
        payments = [
            {"from": users[a], "to": users[b], "amount": c}
            for a, b, c in sharing.suggested_payments(net)
        ]
        context.update(self.month_nav(month))
        context.update(
            balances=[
                {"user": users[uid], "cents": c}
                for uid, c in sorted(net.items(), key=lambda item: -item[1])
            ],
            payments=payments,
            expenses=sharing.split_expenses(user, household, first, following),
            settlements=sharing.settlements_for(user, household)[:20],
            colors={uid: m.color for uid, m in members.items()},
            shares=[(m.user, m.default_share_bp) for m in members.values()],
            is_admin=self.request.membership.is_admin,
            settlement_form=kwargs.get("settlement_form")
            or SettlementForm(household=household, initial={"from_user": user}),
        )
        return context


class SettlementCreateView(FinanceMixin, View):
    def post(self, request):
        form = SettlementForm(request.POST, household=request.household)
        if form.is_valid():
            d = form.cleaned_data
            try:
                sharing.create_settlement(
                    request.household,
                    request.user,
                    d["from_user"],
                    d["to_user"],
                    d["amount"],
                    d["date"],
                    d["note"],
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Pago registrado."))
                return redirect("finance:shared")
        view = SharedView()
        view.setup(request)
        return view.render_to_response(view.get_context_data(settlement_form=form), status=400)


class SettlementDeleteView(FinanceMixin, View):
    def post(self, request, pk):
        settlement = get_object_or_404(
            sharing.settlements_for(request.user, request.household), pk=pk
        )
        sharing.delete_settlement(settlement, request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect("finance:shared")


class DefaultSplitView(FinanceMixin, View):
    """Reparto por defecto del hogar (solo administración)."""

    def post(self, request):
        if not request.membership.is_admin:
            raise PermissionDenied
        try:
            shares = {}
            for uid in _members(request.household):
                raw = request.POST.get(f"share_{uid}", "0").replace(",", ".")
                shares[uid] = round(float(raw) * 100)
            sharing.set_default_shares(request.household, request.membership, shares)
        except ValueError:
            messages.error(request, _("Revisa los porcentajes."))
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Reparto por defecto guardado."))
        return redirect(reverse("finance:shared") + "#reparto")


# --- Presupuestos -------------------------------------------------------------------------


class BudgetsView(FinanceMixin, View):
    template_name = "finance/budgets.html"

    def form(self, data=None, **kwargs):
        return BudgetForm(data, user=self.request.user, household=self.request.household, **kwargs)

    def render_page(self, form, status=200):
        user, household = self.request.user, self.request.household
        services.ensure_default_categories(household, user)
        month = _month(self.request.GET.get("mes"))
        context = {"form": form, "rows": planning.budget_progress(user, household, month)}
        context.update(self.month_nav(month))
        return render(self.request, self.template_name, context, status=status)

    def get(self, request):
        initial = {}
        if request.GET.get("categoria", "").isdigit():
            initial["category"] = int(request.GET["categoria"])
        return self.render_page(self.form(initial=initial))

    def post(self, request):
        form = self.form(request.POST)
        if form.is_valid():
            try:
                planning.set_budget(
                    request.household,
                    request.user,
                    form.cleaned_data["category"],
                    form.cleaned_data["amount"],
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Presupuesto guardado."))
                return redirect("finance:budgets")
        return self.render_page(form, status=400)


# --- Ahorro -------------------------------------------------------------------------------


class GoalsView(FinanceMixin, View):
    template_name = "finance/goals.html"

    def form(self, data=None, **kwargs):
        return GoalForm(data, user=self.request.user, household=self.request.household, **kwargs)

    def render_page(self, form, status=200):
        goals = list(planning.goals_for(self.request.user, self.request.household))
        context = {"form": form, "rows": planning.goal_progress(goals)}
        return render(self.request, self.template_name, context, status=status)

    def get(self, request):
        return self.render_page(self.form())

    def post(self, request):
        form = self.form(request.POST)
        if form.is_valid():
            try:
                planning.create_goal(request.household, request.user, **form.goal_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Meta creada."))
                return redirect("finance:goals")
        return self.render_page(form, status=400)


class GoalMixin(FinanceMixin):
    def get_goal(self, pk, editable=False):
        visible = planning.goals_for(self.request.user, self.request.household)
        goal = get_object_or_404(visible, pk=pk)
        if editable and not goal.can_edit(self.request.user):
            raise Http404
        return goal


class GoalEditView(GoalMixin, View):
    template_name = "finance/goal_form.html"

    def context(self, goal, form):
        can_delete = goal.can_delete(self.request.user, self.request.membership)
        return {"form": form, "goal": goal, "can_delete": can_delete}

    def form(self, goal, data=None):
        return GoalForm(data, user=self.request.user, household=self.request.household, goal=goal)

    def get(self, request, pk):
        goal = self.get_goal(pk, editable=True)
        return render(request, self.template_name, self.context(goal, self.form(goal)))

    def post(self, request, pk):
        goal = self.get_goal(pk, editable=True)
        form = self.form(goal, request.POST)
        if form.is_valid():
            try:
                planning.update_goal(goal, request.user, **form.goal_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("finance:goals")
        return render(request, self.template_name, self.context(goal, form), status=400)


class GoalContributeView(GoalMixin, View):
    def post(self, request, pk):
        goal = self.get_goal(pk, editable=True)
        form = ContributionForm(request.POST)
        if not form.is_valid():
            messages.error(request, " ".join(form.errors.get("amount", [])))
            return redirect("finance:goals")
        try:
            planning.contribute(goal, request.user, form.cleaned_data["amount"])
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Aportación apuntada."))
        return redirect("finance:goals")


class GoalDeleteView(GoalMixin, View):
    def post(self, request, pk):
        planning.delete_goal(self.get_goal(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect("finance:goals")
