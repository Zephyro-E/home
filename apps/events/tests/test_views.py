"""Vistas del calendario: funcionamiento y autorización (otro miembro, otro hogar, anónimo)."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Visibility
from apps.events import services
from apps.events.models import Event
from apps.tasks import services as tasks

pytestmark = pytest.mark.django_db
UNDO = {"HTTP_X_UNDO_COMMIT": "1"}


def allday(household, owner, title, day, **extra):
    return services.create_event(
        household, owner, title=title, all_day=True, start_date=day, end_date=day, **extra
    )


@pytest.fixture
def data(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    today = timezone.localdate()
    return {
        "household": household,
        "ana": ana,
        "luis": luis,
        "eva": eva,
        "today": today,
        "shared": allday(household, ana, "Cena familiar", today),
        "private": allday(household, ana, "Sorpresa", today, visibility=Visibility.PRIVATE),
        "foreign": allday(other, eva, "Fiesta ajena", today),
    }


PAGES = ["calendar:month", "calendar:week", "calendar:agenda", "calendar:create"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    response = client.get(reverse(name))
    assert response.status_code == 302 and reverse("core:login") in response.url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


@pytest.mark.parametrize("name", ["calendar:month", "calendar:week", "calendar:agenda"])
def test_vistas_muestran_solo_lo_visible(login_as, data, name):
    html = login_as(data["luis"]).get(reverse(name)).content.decode()
    assert "Cena familiar" in html
    assert "Sorpresa" not in html and "Fiesta ajena" not in html


@pytest.mark.parametrize("query", ["?mes=2026-13", "?mes=abc", "?dia=2026-02-30", "?mes=1-1"])
def test_parametros_raros_no_rompen(login_as, data, query):
    assert login_as(data["luis"]).get(reverse("calendar:month") + query).status_code == 200
    assert login_as(data["luis"]).get(reverse("calendar:week") + query).status_code == 200


def test_mes_con_dia_seleccionado(login_as, data):
    tasks.create_task(data["household"], data["ana"], "Pagar seguro", due_date=date(2027, 2, 10))
    html = (
        login_as(data["luis"])
        .get(reverse("calendar:month") + "?mes=2027-02&dia=2027-02-10")
        .content.decode()
    )
    assert "Pagar seguro" in html and "febrero" in html.lower()


@pytest.mark.parametrize("name", ["calendar:detail", "calendar:edit"])
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_evento_ajeno_da_404(login_as, data, name, who, target):
    assert login_as(data[who]).get(reverse(name, args=[data[target].pk])).status_code == 404


@pytest.mark.parametrize("name", ["calendar:edit", "calendar:share", "calendar:delete"])
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_evento_ajeno_no_se_modifica(login_as, data, name, who, target):
    event = data[target]
    payload = {"title": "Hackeado", "kind": "general", "start_date": "2026-11-20", "all_day": "on"}
    response = login_as(data[who]).post(reverse(name, args=[event.pk]), payload, **UNDO)
    assert response.status_code == 404
    event.refresh_from_db()
    assert event.title != "Hackeado"


def test_crear_evento_con_hora_y_repeticion(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("calendar:create"),
        {
            "title": "Inglés",
            "kind": "appointment",
            "visibility": "shared",
            "start_date": "2026-11-18",
            "start_time": "18:00",
            "end_time": "19:30",
            "location": "Academia",
            "participants": [data["luis"].pk],
            "repeat_freq": "WEEKLY",
            "repeat_interval": "1",
        },
    )
    event = Event.objects.get(title="Inglés")
    assert response.status_code == 302
    local = timezone.localtime(event.starts_at)
    assert (local.hour, local.minute) == (18, 0)
    assert event.ends_at - event.starts_at == timedelta(minutes=90)
    assert event.recurrence_rule == "FREQ=WEEKLY"
    assert list(event.participants.all()) == [data["luis"]]


def test_crear_sin_hora_final_dura_una_hora(login_as, data):
    login_as(data["luis"]).post(
        reverse("calendar:create"),
        {
            "title": "Médico",
            "kind": "appointment",
            "visibility": "shared",
            "start_date": "2026-11-18",
            "start_time": "10:00",
        },
    )
    event = Event.objects.get(title="Médico")
    assert event.ends_at - event.starts_at == timedelta(hours=1)


@pytest.mark.parametrize(
    "extra",
    [
        {"start_time": ""},  # ni hora ni "todo el día"
        {"start_time": "10:00", "end_date": "2026-11-17"},  # final antes
        {"all_day": "on", "end_date": "2026-11-01"},
    ],
)
def test_crear_evento_invalido(login_as, data, extra):
    payload = {"title": "X", "kind": "general", "visibility": "shared", "start_date": "2026-11-18"}
    response = login_as(data["luis"]).post(reverse("calendar:create"), {**payload, **extra})
    assert response.status_code == 400
    assert not Event.objects.filter(title="X").exists()


def test_participante_de_otro_hogar_rechazado(login_as, data):
    response = login_as(data["ana"]).post(
        reverse("calendar:create"),
        {
            "title": "X",
            "kind": "general",
            "visibility": "shared",
            "start_date": "2026-11-18",
            "all_day": "on",
            "participants": [data["eva"].pk],
        },
    )
    assert response.status_code == 400


def test_editar_evento_compartido(login_as, data):
    event = data["shared"]
    client = login_as(data["luis"])
    form = client.get(reverse("calendar:edit", args=[event.pk])).content.decode()
    assert "Cena familiar" in form
    response = client.post(
        reverse("calendar:edit", args=[event.pk]),
        {"title": "Cena", "kind": "celebration", "start_date": "2026-11-20", "start_time": "21:00"},
    )
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.title == "Cena" and not event.all_day and event.kind == "celebration"


def test_detalle_de_una_repeticion(login_as, data):
    event = data["shared"]
    event.recurrence_rule = "FREQ=YEARLY"
    event.save()
    next_year = data["today"].replace(year=data["today"].year + 1)
    html = (
        login_as(data["luis"])
        .get(reverse("calendar:detail", args=[event.pk]) + f"?fecha={next_year:%Y-%m-%d}")
        .content.decode()
    )
    assert "Cada año" in html and "Borrar toda la serie" not in html  # Luis no puede borrar


def test_borrar_y_compartir(login_as, data):
    client = login_as(data["ana"])
    client.post(reverse("calendar:share", args=[data["private"].pk]))
    data["private"].refresh_from_db()
    assert data["private"].visibility == Visibility.SHARED
    response = client.post(reverse("calendar:delete", args=[data["shared"].pk]), **UNDO)
    assert response.status_code == 204
    assert not Event.objects.filter(pk=data["shared"].pk).exists()


def test_miembro_no_borra_lo_ajeno(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("calendar:delete", args=[data["shared"].pk]), **UNDO
    )
    assert response.status_code == 403


def test_inicio_muestra_eventos_de_hoy(login_as, data):
    html = login_as(data["luis"]).get(reverse("core:home")).content.decode()
    assert "Para hoy" in html and "Cena familiar" in html and "Sorpresa" not in html


def test_formulario_de_tarea_con_repeticion(login_as, data):
    client = login_as(data["luis"])
    response = client.post(
        reverse("tasks:create"),
        {
            "title": "Regar",
            "visibility": "shared",
            "priority": "medium",
            "status": "todo",
            "due_date": "2026-11-20",
            "repeat_freq": "WEEKLY",
            "repeat_interval": "2",
        },
    )
    assert response.status_code == 302
    from apps.tasks.models import Task

    assert Task.objects.get(title="Regar").recurrence_rule == "FREQ=WEEKLY;INTERVAL=2"
    bad = client.post(
        reverse("tasks:create"),
        {
            "title": "Sin fecha",
            "visibility": "shared",
            "priority": "medium",
            "status": "todo",
            "repeat_freq": "DAILY",
        },
    )
    assert bad.status_code == 400
