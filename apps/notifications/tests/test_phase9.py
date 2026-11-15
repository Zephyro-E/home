"""Fase 9: recuperar contraseña, avisos, buscador y exportación (con su privacidad)."""

import json
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core import search, services
from apps.core.models import Membership, PasswordReset
from apps.events import services as events
from apps.finance import services as finance
from apps.finance import sharing
from apps.media import services as media
from apps.notifications.models import Notification
from apps.recipes import services as recipes
from apps.shopping import services as shopping
from apps.tasks import services as tasks

pytestmark = pytest.mark.django_db


@pytest.fixture
def h(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    return {"household": household, "ana": ana, "luis": luis, "other": other, "eva": eva}


def kinds(user):
    return sorted(Notification.objects.filter(owner=user).values_list("kind", flat=True))


# --- Recuperar contraseña -----------------------------------------------------------------


def test_enlace_de_contrasena_solo_para_miembros(h):
    ana_m = Membership.objects.get(user=h["ana"])
    luis_m = Membership.objects.get(user=h["luis"])
    with pytest.raises(ValidationError):
        services.create_password_reset(luis_m, ana_m)  # Luis no administra
    with pytest.raises(ValidationError):
        services.create_password_reset(ana_m, ana_m)  # uno mismo
    luis_m.role = "admin"
    luis_m.save()
    with pytest.raises(ValidationError):
        services.create_password_reset(ana_m, luis_m)  # otra persona admin


def test_flujo_completo_de_recuperacion(h, client, login_as):
    luis_m = Membership.objects.get(user=h["luis"])
    admin = login_as(h["ana"])
    response = admin.post(reverse("core:member_password_reset", args=[luis_m.pk]))
    assert response.status_code == 302
    page = admin.get(reverse("core:household")).content.decode()
    assert "/recuperar/" in page
    url = page.split('value="http://testserver')[1].split('"')[0]
    admin.logout()
    assert client.get(url).status_code == 200
    bad = client.post(url, {"new_password1": "corta", "new_password2": "corta"})
    assert bad.status_code == 400
    ok = client.post(
        url, {"new_password1": "Otra-clave-larga-99", "new_password2": "Otra-clave-larga-99"}
    )
    assert ok.status_code == 302 and ok.url == reverse("core:login")
    h["luis"].refresh_from_db()
    assert h["luis"].check_password("Otra-clave-larga-99")
    assert client.get(url).status_code == 410  # ya usado
    assert PasswordReset.objects.get().used_at is not None
    # La página del enlace no vuelve a mostrarse en el hogar.
    assert "/recuperar/" not in login_as(h["ana"]).get(reverse("core:household")).content.decode()


def test_enlace_caducado_o_inventado(h, client):
    luis_m = Membership.objects.get(user=h["luis"])
    reset, token = services.create_password_reset(Membership.objects.get(user=h["ana"]), luis_m)
    reset.expires_at = timezone.now()
    reset.save()
    assert client.get(reverse("core:password_reset", args=[token])).status_code == 410
    assert client.get(reverse("core:password_reset", args=["inventado"])).status_code == 410


def test_nuevo_enlace_anula_el_anterior(h):
    ana_m = Membership.objects.get(user=h["ana"])
    luis_m = Membership.objects.get(user=h["luis"])
    _r1, t1 = services.create_password_reset(ana_m, luis_m)
    _r2, t2 = services.create_password_reset(ana_m, luis_m)
    assert PasswordReset.find_valid(t1) is None and PasswordReset.find_valid(t2) is not None


def test_otro_hogar_no_crea_enlaces(h, login_as):
    luis_m = Membership.objects.get(user=h["luis"])
    response = login_as(h["eva"]).post(reverse("core:member_password_reset", args=[luis_m.pk]))
    assert response.status_code == 404


def test_pagina_he_olvidado_la_contrasena(client):
    assert client.get(reverse("core:forgot_password")).status_code in (200, 302)


# --- Avisos -------------------------------------------------------------------------------


def test_avisos_de_tareas_y_comentarios(h):
    hh, ana, luis = h["household"], h["ana"], h["luis"]
    t = tasks.create_task(hh, ana, "Pintar", assignee=luis)
    tasks.create_task(hh, ana, "Mía", assignee=ana)  # a sí misma: sin aviso
    tasks.add_comment(t, luis, "¿Qué color?")
    tasks.update_task(t, ana, assignee=ana)
    assert kinds(luis) == ["task_assigned"]
    assert kinds(ana) == ["comment"]


def test_avisos_de_propuestas_eventos_y_gastos(h):
    hh, ana, luis = h["household"], h["ana"], h["luis"]
    shopping.create_wish(hh, ana, name="Sofá", visibility="shared")
    secreto = shopping.create_wish(hh, ana, name="Regalo", visibility="private")
    assert kinds(luis) == ["wish_proposed"]
    shopping.make_shared(secreto, ana)
    events.create_event(
        hh,
        ana,
        title="Cena",
        all_day=True,
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 1),
        participants=[ana, luis],
    )
    card = finance.create_account(hh, ana, name="Tarjeta", visibility="private")
    finance.create_transaction(
        hh,
        ana,
        kind="expense",
        amount_cents=3000,
        date=date(2026, 11, 20),
        account=card,
        is_split=True,
    )
    sharing.create_settlement(hh, luis, luis, ana, 1500, date(2026, 11, 21))
    assert kinds(luis) == ["event_added", "expense_split", "wish_proposed", "wish_proposed"]
    assert kinds(ana) == ["settlement"]


def test_avisos_no_salen_del_hogar_ni_llegan_a_quien_actua(h):
    from apps.notifications.services import notify

    n = notify(h["household"], [h["ana"], h["luis"], h["eva"]], h["ana"], "comment", "X")
    assert n == 1 and kinds(h["eva"]) == [] and kinds(h["ana"]) == []


def test_comentario_en_receta_avisa_al_duenno(h):
    r = recipes.create_recipe(h["household"], h["ana"], title="Tortilla")
    recipes.add_comment(r, h["luis"], "¡Riquísima!")
    m = media.create_title(h["household"], h["ana"], title="Dune")
    media.add_comment(m, h["luis"], "La vemos")
    assert kinds(h["ana"]) == ["comment", "comment"]


def test_vistas_de_avisos(h, login_as, client):
    tasks.create_task(h["household"], h["ana"], "Pintar", assignee=h["luis"])
    notification = Notification.objects.get(owner=h["luis"])
    luis = login_as(h["luis"])
    home = luis.get(reverse("core:home")).content.decode()
    assert "1 sin leer" in home
    page = luis.get(reverse("notifications:list")).content.decode()
    assert "te ha asignado la tarea" in page and "Pintar" in page
    response = luis.get(reverse("notifications:open", args=[notification.pk]))
    assert response.status_code == 302 and "/tareas/" in response.url
    notification.refresh_from_db()
    assert notification.read_at is not None
    # Nadie más puede abrir el aviso de Luis.
    assert (
        login_as(h["ana"]).get(reverse("notifications:open", args=[notification.pk])).status_code
        == 404
    )
    assert (
        login_as(h["eva"]).get(reverse("notifications:open", args=[notification.pk])).status_code
        == 404
    )
    client.logout()
    assert reverse("core:login") in client.get(reverse("notifications:list")).url


def test_marcar_todo_como_leido(h, login_as):
    tasks.create_task(h["household"], h["ana"], "A", assignee=h["luis"])
    tasks.create_task(h["household"], h["ana"], "B", assignee=h["luis"])
    login_as(h["luis"]).post(reverse("notifications:read_all"))
    assert not Notification.objects.filter(owner=h["luis"], read_at__isnull=True).exists()


def test_aviso_con_url_externa_no_redirige_fuera(h, login_as):
    n = Notification.objects.create(
        household=h["household"],
        owner=h["luis"],
        kind="comment",
        title="X",
        url="https://malicioso.test/",
    )
    response = login_as(h["luis"]).get(reverse("notifications:open", args=[n.pk]))
    assert response.url == reverse("notifications:list")


# --- Buscador -----------------------------------------------------------------------------


def test_busqueda_global_respeta_la_privacidad(h):
    hh, ana, luis = h["household"], h["ana"], h["luis"]
    shopping.add_grocery(hh, ana, "Tomates")
    tasks.create_task(hh, ana, "Plantar tomates")
    tasks.create_task(hh, ana, "Tomates secretos", visibility="private")
    recipes.create_recipe(hh, ana, title="Gazpacho", ingredients_text="1 kg de tomates")
    shopping.add_grocery(h["other"], h["eva"], "Tomates de Eva")
    groups = {g.key: [i[0] for i in g.items] for g in search.search(luis, hh, "tomate")}
    assert groups == {"grocery": ["Tomates"], "tasks": ["Plantar tomates"], "recipes": ["Gazpacho"]}
    assert search.search(luis, hh, "t") == []


def test_vista_de_busqueda(h, login_as):
    tasks.create_task(h["household"], h["ana"], "Revisar caldera")
    client = login_as(h["luis"])
    html = client.get(reverse("core:search") + "?q=caldera").content.decode()
    assert "Revisar caldera" in html
    assert "No hay resultados" in client.get(reverse("core:search") + "?q=zzzz").content.decode()
    assert client.get(reverse("core:search")).status_code == 200


# --- Exportación --------------------------------------------------------------------------


def test_exportar_json_solo_lo_visible(h, login_as):
    hh, ana = h["household"], h["ana"]
    tasks.create_task(hh, ana, "Común")
    tasks.create_task(hh, ana, "Secreta de Ana", visibility="private")
    acc = finance.create_account(hh, ana, name="Nómina Ana", visibility="private")
    common = finance.create_account(hh, ana, name="Común")
    finance.create_transaction(
        hh,
        ana,
        kind="transfer",
        amount_cents=5000,
        date=date(2026, 11, 1),
        account=acc,
        to_account=common,
    )
    response = login_as(h["luis"]).get(reverse("core:export_json"))
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    data = json.loads(response.content)
    assert [t["título"] for t in data["tareas"]] == ["Común"]
    assert [a["cuenta"] for a in data["cuentas"]] == ["Común"]
    assert data["movimientos"][0]["cuenta"] == "Cuenta personal de Ana"
    assert "Nómina Ana" not in response.content.decode()


def test_exportar_csv(h, login_as):
    hh, ana = h["household"], h["ana"]
    common = finance.create_account(hh, ana, name="Común")
    finance.create_transaction(
        hh,
        ana,
        kind="expense",
        amount_cents=4590,
        date=date(2026, 11, 3),
        account=common,
        description="Compra; grande",
    )
    client = login_as(h["luis"])
    response = client.get(reverse("core:export_csv", args=["movimientos"]))
    text = response.content.decode("utf-8")
    assert text.startswith("﻿fecha;tipo;importe")
    assert "45,90" in text and '"Compra; grande"' in text
    assert client.get(reverse("core:export_csv", args=["inventado"])).status_code == 404
    for key in (
        "lista-compra",
        "deseos",
        "tareas",
        "eventos",
        "peliculas",
        "sitios",
        "recetas",
        "cuentas",
    ):
        assert client.get(reverse("core:export_csv", args=[key])).status_code == 200
    assert client.get(reverse("core:export")).status_code == 200


def test_exportar_exige_sesion(client, make_user):
    make_user()
    assert reverse("core:login") in client.get(reverse("core:export_json")).url
