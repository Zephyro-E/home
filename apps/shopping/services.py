"""Lógica de negocio de compras. Las vistas comprueban qué puede ver cada persona;
aquí se aplican las reglas (quién puede editar, cambios de estado, votos)."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import Visibility

from .models import GroceryItem, WishComment, WishItem, WishVote

# --- Lista de la compra -------------------------------------------------------------------


def grocery_for(user, household):
    return GroceryItem.objects.visible_to(user, household).select_related("owner", "checked_by")


def add_grocery(household, user, name: str, quantity: str = "") -> GroceryItem:
    """Añade un producto. Si ya está en la lista no se duplica:
    - pendiente: se actualiza la cantidad (si se indica);
    - ya marcado como comprado: vuelve a quedar pendiente.
    """
    name = " ".join(name.split())
    quantity = quantity.strip()
    if not name:
        raise ValidationError(_("Escribe el nombre del producto."))
    existing = (
        GroceryItem.objects.filter(household=household, name__iexact=name)
        .order_by("is_checked")
        .first()
    )
    if existing:
        if quantity:
            existing.quantity = quantity
        if existing.is_checked:
            existing.is_checked = False
            existing.checked_at = None
            existing.checked_by = None
        existing.save()
        return existing
    return GroceryItem.objects.create(household=household, owner=user, name=name, quantity=quantity)


def set_grocery_checked(item: GroceryItem, user, checked: bool) -> GroceryItem:
    item.is_checked = checked
    item.checked_at = timezone.now() if checked else None
    item.checked_by = user if checked else None
    item.save(update_fields=["is_checked", "checked_at", "checked_by", "updated_at"])
    return item


def delete_groceries(user, household, ids) -> int:
    """Borra los productos indicados (solo los de la lista del hogar). Devuelve cuántos."""
    deleted, _detail = grocery_for(user, household).filter(pk__in=ids).delete()
    return deleted


# --- Deseos -------------------------------------------------------------------------------


def wishes_for(user, household):
    return WishItem.objects.visible_to(user, household).select_related("owner")


def _require_edit(item: WishItem, user):
    if not item.can_edit(user):
        raise PermissionDenied


def create_wish(household, user, **data) -> WishItem:
    return WishItem.objects.create(household=household, owner=user, **data)


def update_wish(item: WishItem, user, **data) -> WishItem:
    _require_edit(item, user)
    # La visibilidad solo cambia con make_shared (de personal a común, nunca al revés).
    data.pop("visibility", None)
    for field, value in data.items():
        setattr(item, field, value)
    item.save()
    return item


def make_shared(item: WishItem, user) -> WishItem:
    """Convierte un deseo personal en propuesta común. Solo su dueño; no se copia."""
    if item.owner_id != user.pk:
        raise PermissionDenied
    if item.visibility != Visibility.SHARED:
        item.visibility = Visibility.SHARED
        item.save(update_fields=["visibility", "updated_at"])
    return item


def change_status(item: WishItem, user, status: str) -> WishItem:
    """Cualquier miembro puede cambiar el estado de una propuesta común (decisión del
    propietario); un deseo personal, solo su dueño. Los votos no lo cambian solos."""
    _require_edit(item, user)
    if status not in WishItem.Status.values:
        raise ValidationError(_("Estado no válido."))
    if item.status != status:
        item.status = status
        item.status_changed_by = user
        item.status_changed_at = timezone.now()
        item.save(update_fields=["status", "status_changed_by", "status_changed_at", "updated_at"])
    return item


def delete_wish(item: WishItem, user, membership) -> None:
    if not item.can_delete(user, membership):
        raise PermissionDenied
    item.delete()


@transaction.atomic
def vote(item: WishItem, user, value: int) -> int | None:
    """Vota +1 o -1. Repetir el mismo voto lo retira. Devuelve el voto resultante (o None).

    Solo se vota en propuestas comunes.
    """
    if not item.is_shared:
        raise ValidationError(_("Solo se vota en las propuestas comunes."))
    if value not in WishVote.Value.values:
        raise ValidationError(_("Voto no válido."))
    current = WishVote.objects.select_for_update().filter(item=item, user=user).first()
    if current and current.value == value:
        current.delete()
        return None
    if current:
        current.value = value
        current.save(update_fields=["value", "updated_at"])
    else:
        WishVote.objects.create(item=item, user=user, value=value)
    return value


def add_comment(item: WishItem, user, body: str) -> WishComment:
    body = body.strip()
    if not body:
        raise ValidationError(_("Escribe un comentario."))
    if not item.is_shared:
        raise ValidationError(_("Solo se comenta en las propuestas comunes."))
    return WishComment.objects.create(item=item, author=user, body=body[:2000])


def delete_comment(comment: WishComment, user) -> None:
    if comment.author_id != user.pk:
        raise PermissionDenied
    comment.delete()


# --- Dashboard ----------------------------------------------------------------------------


def dashboard_summary(user, household) -> dict:
    """Datos para los widgets del inicio: solo se muestran si hay algo que enseñar."""
    pending = grocery_for(user, household).filter(is_checked=False)
    to_vote = (
        wishes_for(user, household)
        .filter(visibility=Visibility.SHARED, status=WishItem.Status.PENDING)
        .exclude(votes__user=user)
    )
    return {
        "grocery_count": pending.count(),
        "grocery_preview": list(pending.values_list("name", flat=True)[:4]),
        "wishes_to_vote": to_vote.count(),
    }
