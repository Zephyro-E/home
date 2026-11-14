"""Lógica de negocio del núcleo: hogares, miembros, invitaciones y protección del login."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import MEMBER_COLORS, Household, Invitation, Membership

User = get_user_model()


# --- Hogares y miembros ------------------------------------------------------------------


def _next_color(household: Household) -> str:
    used = set(household.memberships.values_list("color", flat=True))
    for color in MEMBER_COLORS:
        if color not in used:
            return color
    return MEMBER_COLORS[household.memberships.count() % len(MEMBER_COLORS)]


def add_member(household: Household, user, role=Membership.Role.MEMBER) -> Membership:
    membership, _created = Membership.objects.get_or_create(
        household=household,
        user=user,
        defaults={"role": role, "color": _next_color(household)},
    )
    return membership


@transaction.atomic
def create_household(name: str, admin_user) -> Household:
    household = Household.objects.create(name=name.strip())
    add_member(household, admin_user, role=Membership.Role.ADMIN)
    return household


@transaction.atomic
def setup_first_user(*, household_name: str, name: str, email: str, password: str):
    """Asistente inicial: primera cuenta (con acceso al panel de administración) y su hogar."""
    if User.objects.exists():
        raise ValidationError(_("La configuración inicial ya se realizó."))
    user = User.objects.create_superuser(email=email, name=name, password=password)
    household = create_household(household_name, user)
    return user, household


def _ensure_other_admin(membership: Membership) -> None:
    if membership.is_admin:
        others = membership.household.memberships.filter(role=Membership.Role.ADMIN).exclude(
            pk=membership.pk
        )
        if not others.exists():
            raise ValidationError(
                _("El hogar debe tener al menos una persona con rol de administración.")
            )


@transaction.atomic
def change_role(membership: Membership, role: str) -> Membership:
    if role not in Membership.Role.values:
        raise ValidationError(_("Rol no válido."))
    if role != Membership.Role.ADMIN:
        _ensure_other_admin(membership)
    membership.role = role
    membership.save(update_fields=["role"])
    return membership


@transaction.atomic
def remove_member(membership: Membership) -> None:
    """Quita a alguien del hogar (o lo usa uno mismo para salir). Sus datos privados se
    conservan asociados a su cuenta, pero deja de ver el hogar."""
    _ensure_other_admin(membership)
    membership.delete()


# --- Invitaciones ------------------------------------------------------------------------


def invitation_error(invitation: Invitation | None) -> str | None:
    if invitation is None or not invitation.is_valid:
        return _("La invitación no es válida, ya se utilizó o ha caducado.")
    return None


@transaction.atomic
def accept_invitation(invitation: Invitation, user) -> Membership:
    # Se vuelve a leer dentro de la transacción para que el enlace solo se use una vez.
    invitation = Invitation.objects.get(pk=invitation.pk)
    if error := invitation_error(invitation):
        raise ValidationError(error)
    if Membership.objects.filter(household=invitation.household, user=user).exists():
        raise ValidationError(_("Ya perteneces a este hogar."))
    membership = add_member(invitation.household, user, role=invitation.role)
    invitation.used_at = timezone.now()
    invitation.used_by = user
    invitation.save(update_fields=["used_at", "used_by"])
    return membership


@transaction.atomic
def register_with_invitation(invitation: Invitation, *, name: str, email: str, password: str):
    if error := invitation_error(invitation):
        raise ValidationError(error)
    user = User.objects.create_user(email=email, name=name, password=password)
    accept_invitation(invitation, user)
    return user


# --- Protección contra intentos de inicio de sesión --------------------------------------

LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60


def _login_keys(ip: str, email: str) -> list[str]:
    return [f"login-fail:ip:{ip}", f"login-fail:pair:{ip}:{(email or '').lower()}"]


def login_is_locked(ip: str, email: str) -> bool:
    ip_key, pair_key = _login_keys(ip, email)
    return (
        cache.get(pair_key, 0) >= LOGIN_MAX_FAILURES
        or cache.get(ip_key, 0) >= LOGIN_MAX_FAILURES * 4
    )


def register_login_failure(ip: str, email: str) -> None:
    for key in _login_keys(ip, email):
        cache.add(key, 0, LOGIN_LOCK_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, LOGIN_LOCK_SECONDS)


def reset_login_failures(ip: str, email: str) -> None:
    cache.delete(_login_keys(ip, email)[1])
