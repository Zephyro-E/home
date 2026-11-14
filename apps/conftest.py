"""Utilidades compartidas por las pruebas."""

import pytest
from django.core.cache import cache

from apps.core import services
from apps.core.middleware import SetupRequiredMiddleware
from apps.core.models import Membership, User


@pytest.fixture(autouse=True)
def _reset_state():
    cache.clear()
    SetupRequiredMiddleware._setup_done = False
    yield
    SetupRequiredMiddleware._setup_done = False


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(name=None, email=None, password="clave-de-prueba-123", **extra):
        counter["n"] += 1
        n = counter["n"]
        return User.objects.create_user(
            email=email or f"persona{n}@casa.test",
            name=name or f"Persona {n}",
            password=password,
            **extra,
        )

    return _make


@pytest.fixture
def home(make_user):
    """Un hogar con una persona administradora (ana) y un miembro (luis)."""
    ana = make_user(name="Ana")
    luis = make_user(name="Luis")
    household = services.create_household("Casa", ana)
    services.add_member(household, luis, role=Membership.Role.MEMBER)
    return household, ana, luis


@pytest.fixture
def other_home(make_user):
    """Otro hogar distinto, con su propia administradora (eva)."""
    eva = make_user(name="Eva")
    household = services.create_household("Otra casa", eva)
    return household, eva


@pytest.fixture
def login_as(client):
    def _login(user):
        client.force_login(user)
        return client

    return _login
