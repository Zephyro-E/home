from io import StringIO

import pytest
from django.core.management import call_command
from django.template import Context, Template
from django.urls import reverse

from apps.core.modules import MODULES


@pytest.fixture
def client(login_as, home):
    """Cliente con sesión iniciada como Ana, administradora del hogar de prueba."""
    return login_as(home[1])


@pytest.mark.django_db
def test_inicio_responde_y_muestra_modulos(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert '<html lang="es"' in html
    for module in MODULES:
        assert str(module.label) in html


@pytest.mark.django_db
def test_entrada_en_ingles_si_el_navegador_lo_pide(client):
    client.logout()
    response = client.get(reverse("core:login"), HTTP_ACCEPT_LANGUAGE="en")
    assert '<html lang="en"' in response.content.decode()


@pytest.mark.django_db
def test_cabeceras_de_seguridad(client):
    response = client.get(reverse("core:home"))
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"


@pytest.mark.django_db
def test_htmx_envia_token_csrf(client):
    html = client.get(reverse("core:home")).content.decode()
    assert "hx-headers" in html
    assert "X-CSRFToken" in html


def test_icono_existente_y_desconocido():
    tpl = Template('{% load ui %}{% icon "house" "size-4" %}|{% icon "no-existe" %}')
    out = tpl.render(Context())
    svg, unknown = out.split("|")
    assert svg.startswith("<svg") and 'class="size-4"' in svg and 'aria-hidden="true"' in svg
    assert unknown == ""


def test_icono_rechaza_rutas_raras():
    tpl = Template('{% load ui %}{% icon "../settings" %}')
    assert tpl.render(Context()) == ""


def test_todos_los_iconos_de_modulos_existen():
    from apps.core.templatetags.ui import icon

    for module in MODULES:
        assert icon(module.icon), f"Falta el icono {module.icon}"


@pytest.mark.django_db
def test_no_faltan_migraciones():
    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())


def test_comprobaciones_de_django():
    call_command("check", stdout=StringIO())


def test_traducciones_completas_y_compiladas():
    """Falla si hay textos nuevos sin traducir: ejecutar `manage.py translations update`,
    traducir en locale/en/LC_MESSAGES/django.po y `manage.py translations compile`."""
    call_command("translations", "check", stdout=StringIO())


@pytest.mark.django_db
def test_la_interfaz_se_traduce_al_ingles(client):
    client.logout()
    html = client.get(reverse("core:login"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Log in" in html
    assert "Iniciar sesión" not in html
