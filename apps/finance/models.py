"""Finanzas I: cuentas, categorías y movimientos (ingresos, gastos y transferencias).

Importes en céntimos enteros (ADR-007). Las transferencias entre cuentas son un tipo de
movimiento propio y no cuentan como ingreso ni gasto en los resúmenes.
"""

from django.conf import settings
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
    # Gasto compartido (Fase 7): pagado con una cuenta personal y repartido entre miembros.
    is_split = models.BooleanField(_("gasto compartido"), default=False)

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
    def paid_by_id(self):
        """Quién adelantó el dinero de un gasto compartido: el dueño de la cuenta."""
        return self.account.owner_id

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


class TransactionSplit(models.Model):
    """Parte de un gasto compartido que corresponde a cada persona."""

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="splits")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    share_bp = models.PositiveIntegerField()  # puntos básicos: 10 000 = 100 %
    amount_cents = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "user"], name="finance_one_split_per_user"
            )
        ]

    def __str__(self):
        return f"{self.user}: {self.amount_cents}"


class Settlement(HouseholdOwnedModel):
    """Pago entre miembros para saldar gastos compartidos ("Luis paga 30 € a Ana")."""

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("paga"), on_delete=models.CASCADE, related_name="+"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("recibe"),
        on_delete=models.CASCADE,
        related_name="+",
    )
    amount_cents = models.PositiveBigIntegerField(_("importe"))
    date = models.DateField(_("fecha"))
    note = models.CharField(_("nota"), max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = _("pago entre miembros")
        verbose_name_plural = _("pagos entre miembros")

    def __str__(self):
        return f"{self.from_user} → {self.to_user}: {self.amount_cents}"

    def save(self, *args, **kwargs):
        self.visibility = Visibility.SHARED
        super().save(*args, **kwargs)


class Budget(HouseholdOwnedModel):
    """Presupuesto mensual de una categoría de gastos, común al hogar."""

    category = models.OneToOneField(
        Category, verbose_name=_("categoría"), on_delete=models.CASCADE, related_name="budget"
    )
    amount_cents = models.PositiveBigIntegerField(_("importe mensual"))

    class Meta:
        ordering = ["category__name"]
        verbose_name = _("presupuesto")
        verbose_name_plural = _("presupuestos")

    def __str__(self):
        return f"{self.category}: {self.amount_cents}"

    def save(self, *args, **kwargs):
        self.visibility = Visibility.SHARED
        super().save(*args, **kwargs)


class SavingsGoal(HouseholdOwnedModel):
    """Meta de ahorro. Con cuenta vinculada, el progreso es su saldo; sin ella, se apuntan
    las aportaciones a mano."""

    name = models.CharField(_("nombre"), max_length=100)
    target_cents = models.PositiveBigIntegerField(_("objetivo"))
    account = models.ForeignKey(
        Account,
        verbose_name=_("cuenta vinculada"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="goals",
    )
    saved_cents = models.BigIntegerField(_("ahorrado"), default=0)
    target_date = models.DateField(_("fecha objetivo"), null=True, blank=True)

    class Meta:
        ordering = ["target_date", "name"]
        verbose_name = _("meta de ahorro")
        verbose_name_plural = _("metas de ahorro")

    def __str__(self):
        return self.name


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
