from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import INPUT_CSS, StyledFormMixin
from apps.core.models import MEMBER_COLORS, Visibility
from apps.core.money import cents_to_input, parse_euros

from . import sharing
from .models import Account, Category, Transaction

User = get_user_model()


def _amount(text, *, allow_negative=False, required=True):
    text = (text or "").strip()
    if not text:
        if required:
            raise forms.ValidationError(_("Escribe el importe."))
        return 0
    negative = allow_negative and text.startswith("-")
    cents = parse_euros(text.lstrip("-") if negative else text)
    if cents is None:
        raise forms.ValidationError(_("Escribe un importe válido, por ejemplo 12,50."))
    if cents > 100_000_000_00:
        raise forms.ValidationError(_("El importe es demasiado alto."))
    return -cents if negative else cents


class AccountForm(StyledFormMixin, forms.ModelForm):
    initial_balance = forms.CharField(
        label=_("Saldo inicial (€)"),
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0,00"}),
        help_text=_("Lo que hay en la cuenta al empezar a usar la app. Puede ser negativo."),
    )

    class Meta:
        model = Account
        fields = ["name", "kind", "visibility"]
        widgets = {"visibility": forms.RadioSelect}
        labels = {"visibility": _("¿De quién es?")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].choices = [
            (Visibility.SHARED, _("Común: la ve y la usa todo el hogar")),
            (Visibility.PRIVATE, _("Personal: solo la ves tú")),
        ]
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        if self.instance.pk:
            del self.fields["visibility"]
            self.initial["initial_balance"] = cents_to_input(self.instance.initial_balance_cents)

    def clean_initial_balance(self):
        return _amount(
            self.cleaned_data.get("initial_balance"), allow_negative=True, required=False
        )

    def account_data(self) -> dict:
        data = {
            f: self.cleaned_data[f]
            for f in ("name", "kind", "visibility")
            if f in self.cleaned_data
        }
        data["initial_balance_cents"] = self.cleaned_data["initial_balance"]
        return data


class TransactionForm(StyledFormMixin, forms.Form):
    kind = forms.ChoiceField(
        label=_("Tipo"), choices=Transaction.Kind.choices, widget=forms.RadioSelect
    )
    amount = forms.CharField(
        label=_("Importe (€)"),
        widget=forms.TextInput(
            attrs={"inputmode": "decimal", "placeholder": "0,00", "autofocus": True}
        ),
    )
    date = forms.DateField(
        label=_("Fecha"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    description = forms.CharField(label=_("Concepto"), max_length=200, required=False)
    account = forms.ModelChoiceField(label=_("Cuenta"), queryset=Account.objects.none())
    to_account = forms.ModelChoiceField(
        label=_("A la cuenta"), queryset=Account.objects.none(), required=False
    )
    expense_category = forms.ModelChoiceField(
        label=_("Categoría"),
        queryset=Category.objects.none(),
        required=False,
        empty_label=_("Sin categoría"),
    )
    income_category = forms.ModelChoiceField(
        label=_("Categoría"),
        queryset=Category.objects.none(),
        required=False,
        empty_label=_("Sin categoría"),
    )
    notes = forms.CharField(
        label=_("Notas"), required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    is_split = forms.BooleanField(
        label=_("Gasto compartido: repartir entre el hogar"), required=False
    )

    def __init__(self, *args, user, household, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "kind": instance.kind,
                "amount": cents_to_input(instance.amount_cents),
                "date": instance.date,
                "description": instance.description,
                "account": instance.account,
                "to_account": instance.to_account,
                "expense_category": instance.category if instance.kind == "expense" else None,
                "income_category": instance.category if instance.kind == "income" else None,
                "notes": instance.notes,
                "is_split": instance.is_split,
            }
        super().__init__(*args, **kwargs)
        self.initial.setdefault("date", timezone.localdate())
        self.initial.setdefault("kind", Transaction.Kind.EXPENSE)
        usable = Account.objects.visible_to(user, household).filter(
            Q(visibility=Visibility.SHARED) | Q(owner=user)
        )
        current = [instance.account_id, instance.to_account_id] if instance else []
        accounts = usable.filter(Q(is_archived=False) | Q(pk__in=[c for c in current if c]))
        self.fields["account"].queryset = accounts
        self.fields["to_account"].queryset = accounts
        for field in ("account", "to_account"):
            self.fields[field].label_from_instance = self._account_label
        categories = Category.objects.visible_to(user, household)
        self.fields["expense_category"].queryset = categories.filter(kind=Category.Kind.EXPENSE)
        self.fields["income_category"].queryset = categories.filter(kind=Category.Kind.INCOME)
        self.fields["kind"].widget.attrs["class"] = "sr-only peer"
        self.fields["is_split"].widget.attrs["class"] = "size-5 rounded border-border accent-accent"
        # Un campo de porcentaje por miembro, con el reparto del gasto o el del hogar.
        current = {}
        if instance is not None and instance.is_split:
            current = {s.user_id: s.share_bp for s in instance.splits.all()}
        self.members = []
        for member, bp in sharing.default_shares(household):
            name = f"share_{member.pk}"
            value = current.get(member.pk, bp if not current else 0)
            self.fields[name] = forms.DecimalField(
                label=member.get_short_name(),
                min_value=0,
                max_value=100,
                decimal_places=2,
                required=False,
                initial=Decimal(value) / 100,
                widget=forms.NumberInput(attrs={"step": "0.01", "inputmode": "decimal"}),
            )
            self.fields[name].widget.attrs["class"] = INPUT_CSS
            self.members.append((member, name))

    @staticmethod
    def _account_label(account):
        if account.visibility == Visibility.PRIVATE:
            return f"{account.name} ({_('personal')})"
        return account.name

    def clean_amount(self):
        return _amount(self.cleaned_data.get("amount"))

    def clean(self):
        data = super().clean()
        if data.get("is_split") and data.get("kind") == Transaction.Kind.EXPENSE:
            total = sum((data.get(name) or Decimal(0)) for _m, name in self.members)
            if total != 100:
                raise forms.ValidationError(
                    _("El reparto debe sumar el 100 %% (ahora suma %(n)s %%).")
                    % {"n": total.normalize()}
                )
        return data

    @property
    def split_fields(self):
        return [self[name] for _member, name in self.members]

    def split_shares(self):
        return [
            (member, int((self.cleaned_data.get(name) or 0) * 100)) for member, name in self.members
        ]

    def transaction_data(self) -> dict:
        d = self.cleaned_data
        kind = d["kind"]
        category = {
            Transaction.Kind.EXPENSE: d.get("expense_category"),
            Transaction.Kind.INCOME: d.get("income_category"),
        }.get(kind)
        return {
            "kind": kind,
            "amount_cents": d["amount"],
            "date": d["date"],
            "description": d.get("description", ""),
            "account": d["account"],
            "to_account": d.get("to_account") if kind == Transaction.Kind.TRANSFER else None,
            "category": category,
            "notes": d.get("notes", ""),
            "is_split": d.get("is_split", False),
            "split_shares": self.split_shares() if d.get("is_split") else [],
        }


class CategoryForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label=_("Nombre"), max_length=60)
    kind = forms.ChoiceField(label=_("Tipo"), choices=Category.Kind.choices)
    color = forms.ChoiceField(label=_("Color"), choices=[(c, c) for c in MEMBER_COLORS])


class SettlementForm(StyledFormMixin, forms.Form):
    from_user = forms.ModelChoiceField(label=_("Paga"), queryset=User.objects.none())
    to_user = forms.ModelChoiceField(label=_("Recibe"), queryset=User.objects.none())
    amount = forms.CharField(
        label=_("Importe (€)"), widget=forms.TextInput(attrs={"inputmode": "decimal"})
    )
    date = forms.DateField(
        label=_("Fecha"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    note = forms.CharField(label=_("Nota"), max_length=200, required=False)

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, **kwargs)
        members = User.objects.filter(memberships__household=household).order_by("name")
        for name in ("from_user", "to_user"):
            self.fields[name].queryset = members
            self.fields[name].label_from_instance = lambda u: u.name or u.email
        self.initial.setdefault("date", timezone.localdate())

    def clean_amount(self):
        return _amount(self.cleaned_data.get("amount"))


class BudgetForm(StyledFormMixin, forms.Form):
    category = forms.ModelChoiceField(label=_("Categoría"), queryset=Category.objects.none())
    amount = forms.CharField(
        label=_("Importe al mes (€)"),
        widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0,00"}),
        help_text=_("Pon 0 para quitar el presupuesto."),
    )

    def __init__(self, *args, user, household, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.visible_to(user, household).filter(
            kind=Category.Kind.EXPENSE
        )

    def clean_amount(self):
        return _amount(self.cleaned_data.get("amount"), required=False)


class GoalForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label=_("Nombre"), max_length=100)
    target = forms.CharField(
        label=_("Objetivo (€)"), widget=forms.TextInput(attrs={"inputmode": "decimal"})
    )
    visibility = forms.ChoiceField(
        label=_("¿De quién es?"),
        choices=[
            (Visibility.SHARED, _("Común: la ve todo el hogar")),
            (Visibility.PRIVATE, _("Personal: solo la ves tú")),
        ],
        widget=forms.RadioSelect,
        initial=Visibility.SHARED,
    )
    account = forms.ModelChoiceField(
        label=_("Cuenta vinculada (opcional)"),
        queryset=Account.objects.none(),
        required=False,
        empty_label=_("Ninguna: apuntaré las aportaciones a mano"),
        help_text=_("Si eliges una cuenta, el progreso será su saldo."),
    )
    target_date = forms.DateField(
        label=_("Fecha objetivo (opcional)"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, user, household, goal=None, **kwargs):
        if goal is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "name": goal.name,
                "target": cents_to_input(goal.target_cents),
                "account": goal.account,
                "target_date": goal.target_date,
            }
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.visible_to(user, household).filter(
            Q(visibility=Visibility.SHARED) | Q(owner=user), is_archived=False
        )
        self.fields["visibility"].widget.attrs["class"] = "accent-accent"
        if goal is not None:
            del self.fields["visibility"]

    def clean_target(self):
        return _amount(self.cleaned_data.get("target"))

    def goal_data(self) -> dict:
        d = self.cleaned_data
        data = {
            "name": d["name"],
            "target_cents": d["target"],
            "account": d.get("account"),
            "target_date": d.get("target_date"),
        }
        if "visibility" in d:
            data["visibility"] = d["visibility"]
        return data


class ContributionForm(forms.Form):
    amount = forms.CharField()

    def clean_amount(self):
        return _amount(self.cleaned_data.get("amount"), allow_negative=True)
