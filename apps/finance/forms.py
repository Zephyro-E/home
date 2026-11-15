from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin
from apps.core.models import MEMBER_COLORS, Visibility
from apps.core.money import cents_to_input, parse_euros

from .models import Account, Category, Transaction


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

    @staticmethod
    def _account_label(account):
        if account.visibility == Visibility.PRIVATE:
            return f"{account.name} ({_('personal')})"
        return account.name

    def clean_amount(self):
        return _amount(self.cleaned_data.get("amount"))

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
        }


class CategoryForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label=_("Nombre"), max_length=60)
    kind = forms.ChoiceField(label=_("Tipo"), choices=Category.Kind.choices)
    color = forms.ChoiceField(label=_("Color"), choices=[(c, c) for c in MEMBER_COLORS])
