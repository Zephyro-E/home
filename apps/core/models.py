"""Modelos del núcleo: usuarios, hogares, miembros, invitaciones y el patrón de permisos.

Ver docs/modelo-datos.md y docs/decisiones.md (ADR-005, ADR-006).
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings as conf
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# --- Usuarios ----------------------------------------------------------------------------


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, name, password, **extra_fields):
        if not email:
            raise ValueError(_("El correo electrónico es obligatorio."))
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, name="", password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, name, password, **extra_fields)

    def create_superuser(self, email, name="", password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, name, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)


def avatar_path(instance, filename):
    return f"avatars/{uuid.uuid4().hex}.webp"


class User(AbstractBaseUser, PermissionsMixin):
    """Usuario de la aplicación. Inicia sesión con su correo electrónico."""

    class Theme(models.TextChoices):
        SYSTEM = "system", _("Según el sistema")
        LIGHT = "light", _("Claro")
        DARK = "dark", _("Oscuro")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("correo electrónico"), unique=True)
    name = models.CharField(_("nombre"), max_length=100, blank=True)
    language = models.CharField(
        _("idioma"), max_length=8, choices=conf.LANGUAGES, default=conf.LANGUAGE_CODE
    )
    theme = models.CharField(_("tema"), max_length=8, choices=Theme, default=Theme.SYSTEM)
    is_active = models.BooleanField(_("activo"), default=True)
    is_staff = models.BooleanField(_("acceso al panel de administración"), default=False)
    date_joined = models.DateTimeField(_("fecha de alta"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = _("usuario")
        verbose_name_plural = _("usuarios")
        ordering = ["name", "email"]

    def __str__(self):
        return self.name or self.email

    def save(self, *args, **kwargs):
        # El correo se guarda en minúsculas: "Ana@Casa.es" y "ana@casa.es" son la misma cuenta.
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def get_short_name(self):
        return self.name.split(" ")[0] if self.name else self.email

    avatar = models.ImageField(_("foto"), upload_to=avatar_path, blank=True)

    @property
    def initials(self) -> str:
        parts = (self.name or self.email).replace("@", " ").split()
        return "".join(p[0] for p in parts[:2]).upper()


# --- Hogares -----------------------------------------------------------------------------


class Household(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("nombre"), max_length=80)
    timezone = models.CharField(_("zona horaria"), max_length=64, default="Europe/Madrid")
    currency = models.CharField(_("moneda"), max_length=3, default="EUR")
    settings = models.JSONField(_("configuración"), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        conf.AUTH_USER_MODEL, through="Membership", related_name="households"
    )

    class Meta:
        verbose_name = _("hogar")
        verbose_name_plural = _("hogares")
        ordering = ["name"]

    def __str__(self):
        return self.name


# Colores asignados a los miembros por orden de llegada (avatares, responsables, eventos).
MEMBER_COLORS = ["teal", "violet", "amber", "rose", "sky", "lime", "orange", "fuchsia"]


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", _("Administración")
        MEMBER = "member", _("Miembro")

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        conf.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(_("rol"), max_length=8, choices=Role, default=Role.MEMBER)
    color = models.CharField(_("color"), max_length=16, default="teal")
    # Reparto por defecto de gastos compartidos en puntos básicos (5000 = 50 %). ADR-007.
    default_share_bp = models.PositiveIntegerField(_("reparto por defecto"), default=5000)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("miembro")
        verbose_name_plural = _("miembros")
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["household", "user"], name="unique_membership"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.household}"

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN


# --- Invitaciones (ADR-006) --------------------------------------------------------------

INVITATION_DAYS = 7


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InvitationQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(used_at__isnull=True, expires_at__gt=timezone.now())


class Invitation(models.Model):
    """Enlace de un solo uso para unirse a un hogar. Solo se guarda el hash del token."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="invitations")
    token_hash = models.CharField(max_length=64, unique=True)
    role = models.CharField(max_length=8, choices=Membership.Role, default=Membership.Role.MEMBER)
    created_by = models.ForeignKey(
        conf.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        conf.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    objects = InvitationQuerySet.as_manager()

    class Meta:
        verbose_name = _("invitación")
        verbose_name_plural = _("invitaciones")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.household} ({self.get_role_display()})"

    @classmethod
    def create_for(cls, household, created_by, role=Membership.Role.MEMBER):
        """Crea una invitación y devuelve (invitación, token). El token solo se ve una vez."""
        token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            household=household,
            token_hash=hash_token(token),
            role=role,
            created_by=created_by,
            expires_at=timezone.now() + timedelta(days=INVITATION_DAYS),
        )
        return invitation, token

    @classmethod
    def find_valid(cls, token: str):
        return (
            cls.objects.pending()
            .select_related("household")
            .filter(token_hash=hash_token(token))
            .first()
        )

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


PASSWORD_RESET_HOURS = 24


class PasswordReset(models.Model):
    """Enlace de un solo uso para elegir contraseña nueva (ADR-023).

    Lo crea quien administra el hogar para un miembro que la ha olvidado. Como en las
    invitaciones, solo se guarda el hash del token.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        conf.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_resets"
    )
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="+")
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        conf.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ({self.created_at:%Y-%m-%d})"

    @classmethod
    def create_for(cls, user, household, created_by):
        """Anula los enlaces anteriores de esa persona y crea uno nuevo: (enlace, token)."""
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        token = secrets.token_urlsafe(32)
        reset = cls.objects.create(
            user=user,
            household=household,
            token_hash=hash_token(token),
            created_by=created_by,
            expires_at=timezone.now() + timedelta(hours=PASSWORD_RESET_HOURS),
        )
        return reset, token

    @classmethod
    def find_valid(cls, token: str):
        return (
            cls.objects.filter(
                token_hash=hash_token(token), used_at__isnull=True, expires_at__gt=timezone.now()
            )
            .select_related("user")
            .first()
        )


# --- Patrón común de los módulos (ADR-005) -----------------------------------------------


class Visibility(models.TextChoices):
    PRIVATE = "private", _("Personal")
    SHARED = "shared", _("Compartido")


class HouseholdOwnedQuerySet(models.QuerySet):
    def visible_to(self, user, household):
        """Elementos que `user` puede ver dentro de `household`.

        - Del hogar indicado, y solo si el usuario es miembro.
        - Compartidos, o privados cuyo dueño es el propio usuario.
        Todo queryset de dominio debe partir de aquí.
        """
        if not user.is_authenticated or household is None:
            return self.none()
        if not Membership.objects.filter(household=household, user=user).exists():
            return self.none()
        return self.filter(household=household).filter(
            Q(visibility=Visibility.SHARED) | Q(owner=user)
        )


class HouseholdOwnedModel(models.Model):
    """Base de todo elemento de un módulo: pertenece a un hogar, tiene dueño y visibilidad."""

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="+")
    owner = models.ForeignKey(conf.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    visibility = models.CharField(
        _("visibilidad"), max_length=8, choices=Visibility, default=Visibility.SHARED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = HouseholdOwnedQuerySet.as_manager()

    class Meta:
        abstract = True

    def can_edit(self, user) -> bool:
        """Compartido: cualquier miembro (decisión del propietario). Privado: solo el dueño.

        Se asume que el objeto ya se obtuvo con `visible_to`, que garantiza la pertenencia.
        """
        return self.visibility == Visibility.SHARED or self.owner_id == user.pk

    def can_delete(self, user, membership=None) -> bool:
        if self.owner_id == user.pk:
            return True
        return self.visibility == Visibility.SHARED and bool(membership and membership.is_admin)
