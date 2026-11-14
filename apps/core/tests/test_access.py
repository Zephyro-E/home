"""Acceso: asistente inicial, inicio de sesión, hogar activo y páginas protegidas."""

import pytest
from django.urls import reverse

from apps.core import services
from apps.core.middleware import SESSION_KEY
from apps.core.models import Household, Membership, User

pytestmark = pytest.mark.django_db

PROTECTED = ["core:home", "core:household", "core:profile", "core:password_change"]


# --- Asistente inicial -------------------------------------------------------------------


def test_sin_cuentas_todo_lleva_al_asistente(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 302
    assert response.url == reverse("core:setup")


def test_asistente_crea_cuenta_y_hogar(client):
    response = client.post(
        reverse("core:setup"),
        {
            "household_name": "Casa",
            "name": "Ana",
            "email": "Ana@Casa.test",
            "password1": "una-clave-larga-123",
            "password2": "una-clave-larga-123",
        },
    )
    assert response.status_code == 302
    user = User.objects.get()
    assert user.email == "ana@casa.test" and user.is_superuser
    membership = Membership.objects.get()
    assert membership.household.name == "Casa" and membership.is_admin
    assert client.get(reverse("core:home")).status_code == 200


def test_asistente_rechaza_contrasenas_debiles(client):
    response = client.post(
        reverse("core:setup"),
        {
            "household_name": "Casa",
            "name": "Ana",
            "email": "ana@casa.test",
            "password1": "12345678",
            "password2": "12345678",
        },
    )
    assert response.status_code == 200
    assert not User.objects.exists()


def test_asistente_no_disponible_si_ya_hay_cuentas(client, make_user):
    make_user()
    assert client.get(reverse("core:setup")).status_code == 404


# --- Páginas protegidas ------------------------------------------------------------------


@pytest.mark.parametrize("name", PROTECTED)
def test_anonimo_va_a_la_pagina_de_entrada(client, make_user, name):
    make_user()
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert response.url.startswith(reverse("core:login"))


def test_admin_de_django_exige_permisos(login_as, home):
    _household, _ana, luis = home
    response = login_as(luis).get("/admin/")
    assert response.status_code == 302  # luis no es staff


# --- Inicio de sesión --------------------------------------------------------------------


def test_login_con_email(client, home):
    response = client.post(
        reverse("core:login"), {"username": "PERSONA1@casa.test", "password": "clave-de-prueba-123"}
    )
    assert response.status_code == 302
    assert client.get(reverse("core:home")).status_code == 200


def test_login_se_bloquea_tras_varios_fallos(client, home):
    url = reverse("core:login")
    for _ in range(services.LOGIN_MAX_FAILURES):
        client.post(url, {"username": "persona1@casa.test", "password": "mal"})
    response = client.post(
        url, {"username": "persona1@casa.test", "password": "clave-de-prueba-123"}
    )
    assert response.status_code == 200
    assert "Demasiados intentos" in response.content.decode()


def test_logout_solo_por_post(login_as, home):
    _household, ana, _luis = home
    client = login_as(ana)
    assert client.get(reverse("core:logout")).status_code == 405
    assert client.post(reverse("core:logout")).status_code == 302
    assert client.get(reverse("core:home")).status_code == 302


# --- Hogar activo ------------------------------------------------------------------------


def test_sin_hogar_lleva_a_crear_uno(login_as, make_user, home):
    lonely = make_user()
    client = login_as(lonely)
    response = client.get(reverse("core:home"))
    assert response.url == reverse("core:no_household")
    client.post(reverse("core:no_household"), {"name": "Mi piso"})
    assert Household.objects.filter(name="Mi piso", memberships__user=lonely).exists()
    assert client.get(reverse("core:home")).status_code == 200


def test_cambiar_a_un_hogar_ajeno_da_404(login_as, home, other_home):
    _household, ana, _luis = home
    other, _eva = other_home
    response = login_as(ana).post(reverse("core:switch_household", args=[other.pk]))
    assert response.status_code == 404


def test_cambiar_entre_hogares_propios(login_as, home):
    household, ana, _luis = home
    second = services.create_household("Casa de la playa", ana)
    client = login_as(ana)
    client.post(reverse("core:switch_household", args=[second.pk]))
    assert client.session[SESSION_KEY] == str(second.pk)
    assert "Casa de la playa" in client.get(reverse("core:home")).content.decode()


def test_hogar_en_sesion_sin_pertenencia_se_descarta(login_as, home, other_home):
    _household, ana, _luis = home
    other, _eva = other_home
    client = login_as(ana)
    session = client.session
    session[SESSION_KEY] = str(other.pk)  # p. ej. la expulsaron de ese hogar
    session.save()
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert "Otra casa" not in response.content.decode()
    assert client.session[SESSION_KEY] != str(other.pk)


def test_idioma_del_perfil(login_as, home):
    _household, ana, _luis = home
    ana.language = "en"
    ana.save()
    html = login_as(ana).get(reverse("core:home")).content.decode()
    assert '<html lang="en"' in html
