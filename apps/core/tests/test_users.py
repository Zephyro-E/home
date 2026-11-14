import pytest
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from django.test import override_settings

User = get_user_model()

pytestmark = pytest.mark.django_db


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])
def test_create_user_normaliza_email_y_usa_argon2():
    user = User.objects.create_user(email="  Ana@Casa.ES ", name="Ana", password="clave-segura-123")
    assert user.email == "ana@casa.es"
    assert user.password.startswith("argon2")
    assert user.check_password("clave-segura-123")
    assert not user.is_staff
    assert not user.is_superuser


def test_email_unico_sin_distinguir_mayusculas():
    User.objects.create_user(email="ana@casa.es", password="x")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="ANA@casa.es", password="y")


def test_create_superuser():
    admin = User.objects.create_superuser(email="admin@casa.es", name="Admin", password="x")
    assert admin.is_staff
    assert admin.is_superuser


def test_login_con_email_en_mayusculas():
    User.objects.create_user(email="ana@casa.es", password="clave-segura-123")
    assert authenticate(username="ANA@casa.es", password="clave-segura-123") is not None
    assert authenticate(username="ana@casa.es", password="otra") is None


def test_nombre_corto():
    assert User(email="a@b.es", name="Ana María").get_short_name() == "Ana"
    assert User(email="a@b.es").get_short_name() == "a@b.es"


def test_la_configuracion_real_usa_argon2():
    from config import settings as real_settings

    assert real_settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
