"""Modelo de ejemplo, solo para pruebas, que usa el patrón común de permisos (ADR-005)."""

from django.db import models

from apps.core.models import HouseholdOwnedModel


class Note(HouseholdOwnedModel):
    title = models.CharField(max_length=100)

    class Meta:
        app_label = "testapp"
