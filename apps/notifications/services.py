"""Crear y leer avisos. Los módulos llaman a notify() desde sus services.

Reglas: nunca se avisa a quien hace la acción; solo a miembros actuales del hogar; y solo
de elementos que la persona avisada ya puede ver (lo comprueba quien llama).
"""

from datetime import timedelta

from django.utils import timezone

from apps.core.models import Membership

from .models import Notification

KEEP_DAYS = 90


def notify(household, recipients, actor, kind: str, title: str, url: str = "") -> int:
    """Crea un aviso para cada persona de `recipients` (usuarios). Devuelve cuántos."""
    member_ids = set(
        Membership.objects.filter(household=household).values_list("user_id", flat=True)
    )
    ids = {u.pk for u in recipients if u is not None} & member_ids
    ids.discard(getattr(actor, "pk", None))
    Notification.objects.bulk_create(
        Notification(
            household=household,
            owner_id=uid,
            actor=actor,
            kind=kind,
            title=str(title)[:200],
            url=url[:300],
            visibility="private",
        )
        for uid in ids
    )
    return len(ids)


def notifications_for(user, household):
    return Notification.objects.visible_to(user, household).select_related("actor")


def unread_count(user, household) -> int:
    if household is None or not user.is_authenticated:
        return 0
    return notifications_for(user, household).filter(read_at__isnull=True).count()


def mark_all_read(user, household) -> None:
    notifications_for(user, household).filter(read_at__isnull=True).update(read_at=timezone.now())


def mark_read(notification) -> None:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])


def purge_old(user, household) -> None:
    """Borra los avisos leídos de más de KEEP_DAYS días."""
    limit = timezone.now() - timedelta(days=KEEP_DAYS)
    notifications_for(user, household).filter(read_at__isnull=False, created_at__lt=limit).delete()
