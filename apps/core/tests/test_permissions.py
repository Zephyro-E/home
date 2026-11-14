"""Patrón común de permisos (ADR-005), probado con un modelo de ejemplo."""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.core.models import Visibility
from apps.core.tests.testapp.models import Note

pytestmark = pytest.mark.django_db


@pytest.fixture
def notes(home):
    household, ana, luis = home
    return {
        "ana_private": Note.objects.create(
            household=household, owner=ana, title="privada de Ana", visibility=Visibility.PRIVATE
        ),
        "ana_shared": Note.objects.create(
            household=household, owner=ana, title="compartida de Ana", visibility=Visibility.SHARED
        ),
        "luis_private": Note.objects.create(
            household=household, owner=luis, title="privada de Luis", visibility=Visibility.PRIVATE
        ),
    }


def titles(qs):
    return set(qs.values_list("title", flat=True))


def test_cada_uno_ve_lo_compartido_y_solo_lo_suyo_privado(home, notes):
    household, ana, luis = home
    assert titles(Note.objects.visible_to(ana, household)) == {
        "privada de Ana",
        "compartida de Ana",
    }
    assert titles(Note.objects.visible_to(luis, household)) == {
        "compartida de Ana",
        "privada de Luis",
    }


def test_la_administracion_no_ve_lo_privado_ajeno(home, notes):
    household, ana, _luis = home  # ana es admin
    assert "privada de Luis" not in titles(Note.objects.visible_to(ana, household))


def test_alguien_de_otro_hogar_no_ve_nada(home, other_home, notes):
    household, _ana, _luis = home
    _other, eva = other_home
    assert not Note.objects.visible_to(eva, household).exists()


def test_anonimo_o_sin_hogar_no_ve_nada(home, notes):
    household, ana, _luis = home
    assert not Note.objects.visible_to(AnonymousUser(), household).exists()
    assert not Note.objects.visible_to(ana, None).exists()


def test_los_elementos_de_otro_hogar_no_se_cuelan(home, other_home, notes):
    household, ana, _luis = home
    other, eva = other_home
    Note.objects.create(household=other, owner=eva, title="de Eva", visibility=Visibility.SHARED)
    assert "de Eva" not in titles(Note.objects.visible_to(ana, household))


def test_editar_y_borrar(home, notes):
    household, ana, luis = home
    ana_m = household.memberships.get(user=ana)
    luis_m = household.memberships.get(user=luis)
    shared = notes["ana_shared"]
    private = notes["ana_private"]

    # Compartido: cualquier miembro edita; borra el dueño o la administración.
    assert shared.can_edit(luis)
    assert shared.can_delete(ana, ana_m)
    assert not shared.can_delete(luis, luis_m)
    luis_shared = Note.objects.create(household=household, owner=luis, title="x")
    assert luis_shared.can_delete(ana, ana_m)

    # Privado: solo el dueño.
    assert private.can_edit(ana)
    assert not private.can_edit(luis)
    assert not notes["luis_private"].can_delete(ana, ana_m)
