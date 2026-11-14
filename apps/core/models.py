"""Modelos del núcleo.

En la Fase 0 solo existe el usuario propio (obligatorio definirlo antes de la primera
migración). Hogares, miembros e invitaciones llegan en la Fase 1 (ver docs/modelo-datos.md).
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


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


class User(AbstractBaseUser, PermissionsMixin):
    """Usuario de la aplicación. Inicia sesión con su correo electrónico."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("correo electrónico"), unique=True)
    name = models.CharField(_("nombre"), max_length=100, blank=True)
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
