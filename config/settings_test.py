"""Ajustes para las pruebas automáticas: añade una app de ejemplo y acelera las contraseñas."""

from .settings import *  # noqa: F403
from .settings import INSTALLED_APPS

INSTALLED_APPS = [*INSTALLED_APPS, "apps.core.tests.testapp"]
# Argon2 es lento a propósito; en pruebas basta un algoritmo rápido.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
