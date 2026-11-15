from django import template
from django.utils.translation import gettext as _

from apps.core.money import format_euros

register = template.Library()


@register.simple_tag
def account_label(account, user):
    """Nombre de la cuenta, o "Cuenta personal de X" si quien mira no puede verla."""
    if account is None:
        return ""
    if account.usable_by(user):
        return account.name
    return _("Cuenta personal de %(name)s") % {"name": account.owner.get_short_name()}


@register.filter
def signed_euros(tx):
    """Importe con signo según el tipo: −12,50 € / +12,50 € / 12,50 € (transferencia)."""
    text = format_euros(tx.amount_cents)
    if tx.kind == "expense":
        return f"−{text}"
    if tx.kind == "income":
        return f"+{text}"
    return text


@register.filter
def can_edit_tx(tx, user):
    return tx.can_edit(user)


@register.filter
def bp_percent(bp):
    """Puntos básicos como porcentaje para un campo numérico: 3333 → "33.33", 5000 → "50"."""
    whole, rest = divmod(int(bp or 0), 100)
    return f"{whole}.{rest:02d}".rstrip("0").rstrip(".") if rest else str(whole)
