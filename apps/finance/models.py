"""Finanzas I: cuentas, categorías y movimientos (ingresos, gastos y transferencias).

Importes en céntimos enteros (ADR-007). Las transferencias entre cuentas son un tipo de
movimiento propio y no cuentan como ingreso ni gasto en los resúmenes.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import MEMBER_COLORS, HouseholdOwnedModel, Visibility


class Account(HouseholdOwnedModel):
    """Cuenta común (la ve y usa todo el hogar) o personal (solo su dueño)."""

    class Kind(models.TextChoices):
        BANK = "bank", _("Cuenta bancaria")
        CASH = "cash", _("Efectivo")
        CARD = "card", _("Tarjeta")
        SAVINGS = "savings", _("Ahorro")

    name = models.CharField(_("nombre"), max_length=80)
    kind = models.CharField(_("tipo"), max_length=8, choices=Kind, default=Kind.BANK)
    initial_balance_cents = models.BigIntegerField(_("saldo inicial"), default=0)
    is_archived = models.BooleanField(_("archivada"), default=False)

    class Meta:
        ordering = ["is_archived", "name"]
        verbose_name = _("cuenta")
        verbose_name_plural = _("cuentas")

    def __str__(self):
        return self.name

    def usable_by(self, user) -> bool:
        return self.visibility == Visibility.SHARED or self.owner_id == user.pk


class Category(HouseholdOwnedModel):
    """Categoría de ingresos o de gastos, común a todo el hogar."""

    class Kind(models.TextChoices):
        EXPENSE = "expense", _("Gasto")
        INCOME = "income", _("Ingreso")

    name = models.CharField(_("nombre"), max_length=60)
    kind = models.CharField(_("tipo"), max_length=8, choices=Kind, default=Kind.EXPENSE)
    color = models.CharField(_("color"), max_length=12, default="teal")

    class Meta:
        ordering = ["kind", "name"]
        verbose_name = _("categoría")
        verbose_name_plural = _("categorías")
        constraints = [
            models.UniqueConstraint(
                fields=["household", "kind", "name"], name="finance_unique_category"
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.visibility = Visibility.SHARED
        if self.color not in MEMBER_COLORS:
            self.color = MEMBER_COLORS[0]
        super().save(*args, **kwargs)


class Transaction(HouseholdOwnedModel):
    class Kind(models.TextChoices):
        EXPENSE = "expense", _("Gasto")
        INCOME = "income", _("Ingreso")
        TRANSFER = "transfer", _("Transferencia")

    kind = models.CharField(_("tipo"), max_length=8, choices=Kind, default=Kind.EXPENSE)
    amount_cents = models.PositiveBigIntegerField(_("importe"))
    date = models.DateField(_("fecha"))
    account = models.ForeignKey(
        Account, verbose_name=_("cuenta"), on_delete=models.PROTECT, related_name="transactions"
    )
    to_account = models.ForeignKey(
        Account,
        verbose_name=_("cuenta de destino"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incoming",
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("categoría"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    description = models.CharField(_("concepto"), max_length=200, blank=True)
    notes = models.TextField(_("notas"), blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = _("movimiento")
        verbose_name_plural = _("movimientos")
        indexes = [models.Index(fields=["household", "date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_cents__gt=0), name="finance_amount_positive"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind="transfer", to_account__isnull=False)
                    | (~models.Q(kind="transfer") & models.Q(to_account__isnull=True))
                ),
                name="finance_transfer_has_destination",
            ),
        ]

    def __str__(self):
        return self.description or self.get_kind_display()

    @property
    def is_transfer(self) -> bool:
        return self.kind == self.Kind.TRANSFER

    def can_edit(self, user) -> bool:
        """Además de la regla común, hay que poder usar todas las cuentas implicadas."""
        accounts = [self.account] + ([self.to_account] if self.to_account_id else [])
        return super().can_edit(user) and all(a.usable_by(user) for a in accounts)

    def can_delete(self, user, membership=None) -> bool:
        accounts = [self.account] + ([self.to_account] if self.to_account_id else [])
        return super().can_delete(user, membership) and all(a.usable_by(user) for a in accounts)


DEFAULT_CATEGORIES = {
    Category.Kind.EXPENSE: [
        (_("Supermercado"), "lime"),
        (_("Casa y facturas"), "sky"),
        (_("Restaurantes"), "orange"),
        (_("Transporte"), "violet"),
        (_("Ocio"), "fuchsia"),
        (_("Salud"), "rose"),
        (_("Ropa"), "amber"),
        (_("Otros gastos"), "teal"),
    ],
    Category.Kind.INCOME: [
        (_("Nómina"), "teal"),
        (_("Otros ingresos"), "lime"),
    ],
}
