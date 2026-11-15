"""Calendario: repeticiones, expansión, proyección de tareas y tareas recurrentes."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core import recurrence
from apps.core.models import Visibility
from apps.events import services
from apps.events.models import Event
from apps.tasks import services as tasks
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db
MADRID = ZoneInfo("Europe/Madrid")


@pytest.fixture(autouse=True)
def _madrid():
    with timezone.override(MADRID):
        yield


def timed(household, owner, title, start, hours=1, **extra):
    start = start.replace(tzinfo=MADRID)
    return services.create_event(
        household,
        owner,
        title=title,
        all_day=False,
        starts_at=start,
        ends_at=start + timedelta(hours=hours),
        **extra,
    )


def allday(household, owner, title, start, end=None, **extra):
    return services.create_event(
        household,
        owner,
        title=title,
        all_day=True,
        start_date=start,
        end_date=end or start,
        **extra,
    )


def titles(days, day):
    return [i.title for i in days[day]]


# --- Reglas -------------------------------------------------------------------------------


def test_construir_y_leer_reglas():
    rule = recurrence.build_rule("WEEKLY", 2, date(2027, 3, 1))
    assert rule == "FREQ=WEEKLY;INTERVAL=2;UNTIL=20270301T235959"
    assert recurrence.parse_rule(rule) == {
        "freq": "WEEKLY",
        "interval": 2,
        "until": date(2027, 3, 1),
    }
    assert recurrence.build_rule("", 3) == ""
    assert recurrence.build_rule("HOURLY") == ""  # no se ofrece
    assert recurrence.parse_rule("FREQ=XX;FOO=1") == {"freq": "", "interval": 1, "until": None}


def test_describir_reglas():
    assert recurrence.describe("FREQ=DAILY") == "Cada día"
    assert recurrence.describe("FREQ=MONTHLY;INTERVAL=3") == "Cada 3 meses"
    assert "01/03/2027" in recurrence.describe("FREQ=YEARLY;UNTIL=20270301T235959")
    assert recurrence.describe("") == ""


def test_siguiente_fecha():
    assert recurrence.next_date("FREQ=WEEKLY", date(2026, 11, 16)) == date(2026, 11, 23)
    assert recurrence.next_date("FREQ=DAILY;UNTIL=20261116T235959", date(2026, 11, 16)) is None


# --- Expansión ----------------------------------------------------------------------------


def test_evento_simple_y_rango(home):
    household, ana, _luis = home
    timed(household, ana, "Dentista", datetime(2026, 11, 18, 18, 0))
    days = services.items_between(ana, household, date(2026, 11, 16), date(2026, 11, 22))
    assert titles(days, date(2026, 11, 18)) == ["Dentista"]
    item = days[date(2026, 11, 18)][0]
    assert item.start == datetime(2026, 11, 18, 18, 0)
    assert not item.all_day
    assert (
        services.items_between(ana, household, date(2026, 11, 19), date(2026, 11, 30))[
            date(2026, 11, 20)
        ]
        == []
    )


def test_semanal_mantiene_la_hora_con_el_cambio_de_horario(home):
    household, ana, _luis = home
    # 18:00 en horario de verano; el 25 de octubre de 2026 se cambia al de invierno.
    timed(household, ana, "Inglés", datetime(2026, 10, 14, 18, 0), recurrence_rule="FREQ=WEEKLY")
    days = services.items_between(ana, household, date(2026, 10, 12), date(2026, 11, 8))
    occurrences = [i for items in days.values() for i in items]
    assert [i.day for i in occurrences] == [
        date(2026, 10, 14),
        date(2026, 10, 21),
        date(2026, 10, 28),
        date(2026, 11, 4),
    ]
    assert {i.start.hour for i in occurrences} == {18}


def test_cumpleannos_anual_y_hasta(home):
    household, ana, _luis = home
    allday(household, ana, "Luis", date(1990, 3, 5), kind="birthday", recurrence_rule="FREQ=YEARLY")
    allday(
        household,
        ana,
        "Curso",
        date(2026, 11, 2),
        recurrence_rule="FREQ=WEEKLY;UNTIL=20261116T235959",
    )
    march = services.items_between(ana, household, date(2027, 3, 1), date(2027, 3, 31))
    assert titles(march, date(2027, 3, 5)) == ["Luis"]
    nov = services.items_between(ana, household, date(2026, 11, 1), date(2026, 11, 30))
    curso = [d for d, items in nov.items() if any(i.title == "Curso" for i in items)]
    assert curso == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)]


def test_evento_de_varios_dias(home):
    household, ana, _luis = home
    allday(household, ana, "Vacaciones", date(2026, 12, 28), date(2027, 1, 2))
    timed(household, ana, "Noche fuera", datetime(2026, 12, 5, 22, 0), hours=4)
    days = services.items_between(ana, household, date(2026, 12, 1), date(2026, 12, 31))
    vacaciones = [d for d, items in days.items() if titles(days, d) == ["Vacaciones"]]
    assert vacaciones == [date(2026, 12, d) for d in range(28, 32)]
    assert titles(days, date(2026, 12, 6)) == ["Noche fuera"]
    assert days[date(2026, 12, 6)][0].continues


def test_acaba_a_medianoche_no_ocupa_el_dia_siguiente(home):
    household, ana, _luis = home
    timed(household, ana, "Cena", datetime(2026, 12, 5, 21, 0), hours=3)
    days = services.items_between(ana, household, date(2026, 12, 5), date(2026, 12, 6))
    assert titles(days, date(2026, 12, 5)) == ["Cena"]
    assert days[date(2026, 12, 6)] == []


def test_orden_del_dia_y_tareas_proyectadas(home):
    household, ana, luis = home
    day = date(2026, 11, 20)
    timed(household, ana, "Tarde", datetime(2026, 11, 20, 17, 0))
    timed(household, ana, "Mañana", datetime(2026, 11, 20, 9, 0))
    allday(household, ana, "Santo", day)
    tasks.create_task(household, ana, "Pagar luz", due_date=day, assignee=luis)
    days = services.items_between(luis, household, day, day)
    assert titles(days, day) == ["Pagar luz", "Santo", "Mañana", "Tarde"]
    task_item = days[day][0]
    assert task_item.type == "task" and task_item.participants == [luis]
    assert Event.objects.count() == 3  # las tareas no se copian como eventos


def test_privado_ajeno_no_aparece(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    day = date(2026, 11, 20)
    allday(household, ana, "Sorpresa", day, visibility=Visibility.PRIVATE)
    allday(other, eva, "De otro hogar", day)
    tasks.create_task(household, ana, "Tarea privada", due_date=day, visibility="private")
    assert services.items_between(luis, household, day, day)[day] == []
    assert titles(services.items_between(ana, household, day, day), day) == [
        "Sorpresa",
        "Tarea privada",
    ]


def test_rango_enorme_rechazado(home):
    household, ana, _luis = home
    with pytest.raises(ValueError):
        services.items_between(ana, household, date(2026, 1, 1), date(2028, 1, 1))


# --- Reglas de negocio --------------------------------------------------------------------


def test_participantes_del_hogar_y_privado(home, other_home):
    household, ana, luis = home
    _other, eva = other_home
    with pytest.raises(ValidationError):
        allday(household, ana, "X", date(2026, 11, 20), participants=[eva])
    with pytest.raises(ValidationError):
        allday(household, ana, "X", date(2026, 11, 20), visibility="private", participants=[luis])
    event = allday(household, ana, "Cena", date(2026, 11, 20), participants=[ana, luis])
    assert set(event.participants.all()) == {ana, luis}


def test_final_antes_que_inicio(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        allday(household, ana, "X", date(2026, 11, 20), date(2026, 11, 19))


def test_editar_cambia_de_hora_a_todo_el_dia(home):
    household, ana, luis = home
    event = timed(household, ana, "Revisión", datetime(2026, 11, 20, 10, 0))
    services.update_event(
        event,
        luis,
        title="Revisión coche",
        all_day=True,
        start_date=date(2026, 11, 21),
        end_date=date(2026, 11, 21),
        starts_at=None,
        ends_at=None,
        visibility="private",
    )
    event.refresh_from_db()
    assert event.all_day and event.starts_at is None and event.title == "Revisión coche"
    assert event.visibility == Visibility.SHARED


def test_permisos_de_edicion_y_borrado(home):
    household, ana, luis = home
    private = allday(household, ana, "Mío", date(2026, 11, 20), visibility="private")
    with pytest.raises(PermissionDenied):
        services.update_event(
            private,
            luis,
            title="x",
            all_day=True,
            start_date=date(2026, 11, 20),
            end_date=date(2026, 11, 20),
        )
    shared = allday(household, ana, "Común", date(2026, 11, 20))
    with pytest.raises(PermissionDenied):
        services.delete_event(shared, luis, luis.memberships.get())
    services.delete_event(shared, ana, ana.memberships.get())
    with pytest.raises(PermissionDenied):
        services.make_shared(private, luis)
    services.make_shared(private, ana)


def test_resumen_de_hoy(home):
    household, ana, _luis = home
    today = timezone.localdate()
    allday(household, ana, "Hoy", today)
    allday(household, ana, "Mañana", today + timedelta(days=1))
    assert [i.title for i in services.dashboard_summary(ana, household)["today_events"]] == ["Hoy"]


# --- Tareas recurrentes -------------------------------------------------------------------


def test_terminar_tarea_recurrente_crea_la_siguiente(home):
    household, ana, luis = home
    today = timezone.localdate()
    label = tasks.create_label(household, ana, "Casa", "teal")
    task = tasks.create_task(
        household,
        ana,
        "Basura",
        due_date=today,
        assignee=luis,
        recurrence_rule="FREQ=WEEKLY",
        labels=[label],
    )
    tasks.add_subtask(task, ana, "Reciclaje")
    tasks.set_status(task, luis, Task.Status.DONE)
    new = Task.objects.exclude(pk=task.pk).get()
    assert new.status == Task.Status.TODO
    assert new.due_date == today + timedelta(days=7)
    assert (new.assignee, new.recurrence_rule) == (luis, "FREQ=WEEKLY")
    assert list(new.labels.all()) == [label]
    assert [s.title for s in new.subtasks.all()] == ["Reciclaje"]
    assert not new.subtasks.get().is_done
    # Reabrir y volver a terminar no crea otra.
    tasks.set_status(task, luis, Task.Status.TODO)
    tasks.set_status(task, luis, Task.Status.DONE)
    assert Task.objects.count() == 2


def test_tarea_atrasada_salta_al_futuro(home):
    household, ana, _luis = home
    today = timezone.localdate()
    task = tasks.create_task(
        household, ana, "Regar", due_date=today - timedelta(days=10), recurrence_rule="FREQ=DAILY"
    )
    tasks.move_task(task, ana, Task.Status.DONE, [task.pk])
    assert Task.objects.exclude(pk=task.pk).get().due_date == today + timedelta(days=1)


def test_serie_terminada_no_crea_mas(home):
    household, ana, _luis = home
    today = timezone.localdate()
    rule = recurrence.build_rule("DAILY", 1, today)
    task = tasks.create_task(household, ana, "Último", due_date=today, recurrence_rule=rule)
    tasks.set_status(task, ana, Task.Status.DONE)
    assert Task.objects.count() == 1


def test_tarea_recurrente_necesita_fecha(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        tasks.create_task(household, ana, "Sin fecha", recurrence_rule="FREQ=DAILY")
