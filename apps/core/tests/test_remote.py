"""Acceso desde fuera de casa (Tailscale) y app instalable (service worker)."""

import json
import subprocess

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.core.management.commands import tailscale as ts

STATUS = {"BackendState": "Running", "Self": {"DNSName": "mi-pc.tail1234.ts.net."}}


@pytest.fixture
def fake_tailscale(monkeypatch):
    """Simula el programa tailscale y guarda las órdenes que recibe."""
    calls = []
    state = {"status": STATUS, "serve_rc": 0}

    def fake_run(args):
        calls.append(args[1:])
        if args[1] == "status":
            return subprocess.CompletedProcess(args, 0, json.dumps(state["status"]), "")
        if args[1] == "serve":
            return subprocess.CompletedProcess(args, state["serve_rc"], "", "error de prueba")
        raise AssertionError(args)

    monkeypatch.setattr(ts, "find_tailscale", lambda: "tailscale")
    monkeypatch.setattr(ts, "run", fake_run)
    return calls, state


def test_configurar_escribe_env_y_activa_serve(fake_tailscale, tmp_path):
    calls, _state = fake_tailscale
    env = tmp_path / ".env"
    env.write_text("# mis ajustes\nHOGAR_DEBUG=0\nHOGAR_HTTPS=0\n", encoding="utf-8")
    call_command("tailscale", "configurar", env_file=str(env))
    text = env.read_text(encoding="utf-8")
    assert "# mis ajustes" in text and "HOGAR_DEBUG=0" in text
    assert "HOGAR_HTTPS=1" in text and "HOGAR_HTTPS=0" not in text
    assert "HOGAR_CSRF_TRUSTED_ORIGINS=https://mi-pc.tail1234.ts.net" in text
    assert ["serve", "--bg", "http://127.0.0.1:8000"] in calls


def test_configurar_dos_veces_no_duplica(fake_tailscale, tmp_path):
    env = tmp_path / ".env"
    call_command("tailscale", "configurar", env_file=str(env))
    call_command("tailscale", "configurar", env_file=str(env))
    assert env.read_text(encoding="utf-8").count("HOGAR_CSRF_TRUSTED_ORIGINS=") == 1


@pytest.mark.parametrize(
    "status",
    [
        {"BackendState": "NeedsLogin", "Self": {"DNSName": "x.ts.net."}},
        {"BackendState": "Running", "Self": {"DNSName": ""}},
    ],
)
def test_tailscale_sin_conectar_o_sin_nombre(fake_tailscale, tmp_path, status):
    _calls, state = fake_tailscale
    state["status"] = status
    env = tmp_path / ".env"
    with pytest.raises(CommandError):
        call_command("tailscale", "configurar", env_file=str(env))
    assert not env.exists()


def test_error_al_activar_https(fake_tailscale, tmp_path):
    _calls, state = fake_tailscale
    state["serve_rc"] = 1
    with pytest.raises(CommandError, match="HTTPS"):
        call_command("tailscale", "configurar", env_file=str(tmp_path / ".env"))


def test_quitar(fake_tailscale):
    calls, _state = fake_tailscale
    call_command("tailscale", "quitar")
    assert ["serve", "reset"] in calls


def test_sin_tailscale_instalado(monkeypatch):
    monkeypatch.setattr(ts.shutil, "which", lambda name: None)
    monkeypatch.setattr(ts, "WINDOWS_PATHS", [])
    with pytest.raises(CommandError, match="tailscale.com/download"):
        ts.find_tailscale()


# --- Service worker y página sin conexión ----------------------------------------------------


@pytest.mark.django_db
def test_service_worker_publico(client, make_user):
    make_user()
    response = client.get(reverse("core:service_worker"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/javascript")
    assert response["Cache-Control"] == "no-cache"
    assert b"/sin-conexion/" in response.content
    assert reverse("core:service_worker") == "/sw.js"


@pytest.mark.django_db
def test_pagina_sin_conexion_publica(client, make_user):
    make_user()
    response = client.get(reverse("core:offline"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "No se puede conectar con Hogar" in html
    assert "<style>" in html and 'rel="stylesheet"' not in html  # autónoma


@pytest.mark.django_db
def test_antes_del_asistente_no_redirige_el_service_worker(client):
    assert client.get("/sw.js").status_code == 200
    assert client.get("/sin-conexion/").status_code == 200
