import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_editar_perfil(login_as, home):
    _household, ana, _luis = home
    client = login_as(ana)
    response = client.post(
        reverse("core:profile"),
        {"name": "Ana María", "email": "ana@nuevo.test", "language": "en", "theme": "dark"},
    )
    assert response.status_code == 302
    page = client.get(response.url).content.decode()
    assert "Profile saved." in page  # el aviso ya sale en el idioma nuevo
    ana.refresh_from_db()
    assert (ana.name, ana.email, ana.language, ana.theme) == (
        "Ana María",
        "ana@nuevo.test",
        "en",
        "dark",
    )


def test_no_se_puede_usar_el_email_de_otra_persona(login_as, home):
    _household, ana, luis = home
    response = login_as(ana).post(
        reverse("core:profile"),
        {"name": "Ana", "email": luis.email.upper(), "language": "es", "theme": "system"},
    )
    assert response.status_code == 200
    ana.refresh_from_db()
    assert ana.email != luis.email


def test_guardar_tema(login_as, home):
    _household, ana, _luis = home
    client = login_as(ana)
    assert client.post(reverse("core:save_theme"), {"theme": "dark"}).status_code == 204
    ana.refresh_from_db()
    assert ana.theme == "dark"
    assert client.post(reverse("core:save_theme"), {"theme": "neon"}).status_code == 400
    html = client.get(reverse("core:home")).content.decode()
    assert 'var p = "dark"' in html


def test_cambiar_contrasena(login_as, home):
    _household, ana, _luis = home
    client = login_as(ana)
    response = client.post(
        reverse("core:password_change"),
        {
            "old_password": "clave-de-prueba-123",
            "new_password1": "otra-clave-larga-456",
            "new_password2": "otra-clave-larga-456",
        },
    )
    assert response.status_code == 302
    ana.refresh_from_db()
    assert ana.check_password("otra-clave-larga-456")
    # La sesión sigue abierta tras el cambio.
    assert client.get(reverse("core:home")).status_code == 200
