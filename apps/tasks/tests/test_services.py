"""Reglas de negocio de tareas."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core.models import Visibility
from apps.tasks import services
from apps.tasks.models import Task, TaskLabel

pytestmark = pytest.mark.django_db


def task(household, owner, title="Sacar la basura", **extra):
    return services.create_task(household, owner, title, **extra)


def test_crear_tarea_queda_arriba_de_pendiente(home):
    household, ana, _luis = home
    first = task(household, ana, "Primera")
    second = task(household, ana, "  Segunda   tarea ")
    assert second.title == "Segunda tarea"
    assert second.status == Task.Status.TODO
    assert second.position < first.position


def test_titulo_vacio_falla(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        task(household, ana, "   ")


def test_responsable_debe_ser_del_hogar(home, other_home):
    household, ana, _luis = home
    _other, eva = other_home
    with pytest.raises(ValidationError):
        task(household, ana, assignee=eva)


def test_tarea_personal_solo_para_su_duenno(home):
    household, ana, luis = home
    with pytest.raises(ValidationError):
        task(household, ana, visibility=Visibility.PRIVATE, assignee=luis)
    mine = task(household, ana, visibility=Visibility.PRIVATE, assignee=ana)
    assert mine not in services.tasks_for(luis, household)
    with pytest.raises(ValidationError):
        services.update_task(mine, ana, assignee=luis)


def test_cualquier_miembro_edita_y_mueve_lo_compartido(home):
    household, ana, luis = home
    t = task(household, ana)
    services.update_task(t, luis, title="Bajar la basura", assignee=luis)
    services.set_status(t, luis, Task.Status.DOING)
    t.refresh_from_db()
    assert t.title == "Bajar la basura" and t.assignee == luis
    assert t.status == Task.Status.DOING


def test_lo_personal_ajeno_no_se_edita(home):
    household, ana, luis = home
    t = task(household, ana, visibility=Visibility.PRIVATE)
    for action in (
        lambda: services.update_task(t, luis, title="x"),
        lambda: services.set_status(t, luis, Task.Status.DONE),
        lambda: services.move_task(t, luis, Task.Status.DONE, [t.pk]),
        lambda: services.add_subtask(t, luis, "x"),
    ):
        with pytest.raises(PermissionDenied):
            action()


def test_terminar_guarda_fecha_y_reabrir_la_quita(home):
    household, ana, _luis = home
    t = task(household, ana)
    services.set_status(t, ana, Task.Status.DONE)
    assert t.completed_at is not None
    services.set_status(t, ana, Task.Status.TODO)
    assert t.completed_at is None


def test_estado_no_valido(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        services.set_status(task(household, ana), ana, "archivada")


def test_mover_reordena_la_columna(home):
    household, ana, _luis = home
    a, b, c = (task(household, ana, n) for n in "abc")
    services.move_task(a, ana, Task.Status.DOING, [a.pk])
    services.move_task(b, ana, Task.Status.DOING, [b.pk, a.pk])
    doing = services.board(ana, household)["doing"]
    assert [t.title for t in doing] == ["b", "a"]
    assert [t.title for t in services.board(ana, household)["todo"]] == ["c"]


def test_mover_ignora_ids_ajenos(home, other_home):
    household, ana, _luis = home
    other, eva = other_home
    mine = task(household, ana, "mía")
    theirs = task(other, eva, "suya")
    before = Task.objects.get(pk=theirs.pk).position
    services.move_task(mine, ana, Task.Status.TODO, [theirs.pk, mine.pk])
    assert Task.objects.get(pk=theirs.pk).position == before


def test_borrar_duenno_o_admin(home):
    household, ana, luis = home
    de_ana = task(household, ana)
    with pytest.raises(PermissionDenied):
        services.delete_task(de_ana, luis, luis.memberships.get())
    de_luis = task(household, luis)
    services.delete_task(de_luis, ana, ana.memberships.get())
    assert not Task.objects.filter(pk=de_luis.pk).exists()


def test_compartir_tarea_personal(home):
    household, ana, luis = home
    t = task(household, ana, visibility=Visibility.PRIVATE)
    with pytest.raises(PermissionDenied):
        services.make_shared(t, luis)
    services.make_shared(t, ana)
    assert t in services.tasks_for(luis, household)


def test_subtareas(home):
    household, ana, luis = home
    t = task(household, ana)
    s1 = services.add_subtask(t, luis, "Bolsas")
    services.add_subtask(t, luis, "Reciclaje")
    services.toggle_subtask(s1, luis)
    counted = Task.objects.with_counts().get(pk=t.pk)
    assert (counted.subtask_done, counted.subtask_count) == (1, 2)
    with pytest.raises(ValidationError):
        services.add_subtask(t, luis, " ")


def test_contadores_no_se_multiplican(home):
    household, ana, luis = home
    t = task(household, ana)
    for n in range(3):
        services.add_subtask(t, ana, f"s{n}")
    for n in range(2):
        services.add_comment(t, luis, f"c{n}")
    counted = Task.objects.with_counts().get(pk=t.pk)
    assert (counted.subtask_count, counted.comment_count) == (3, 2)


def test_comentarios_solo_borra_el_autor(home):
    household, ana, luis = home
    c = services.add_comment(task(household, ana), luis, "hecho")
    with pytest.raises(PermissionDenied):
        services.delete_comment(c, ana)
    services.delete_comment(c, luis)


def test_etiquetas(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    casa = services.create_label(household, ana, "Cocina", "violet")
    with pytest.raises(ValidationError):
        services.create_label(household, luis, "cocina", "teal")
    raro = services.create_label(household, ana, "Raro", "negro")
    assert raro.color == "teal"
    ajena = services.create_label(other, eva, "Jardín", "lime")
    t = task(household, ana, labels=[casa, ajena])  # la ajena se ignora
    assert list(t.labels.all()) == [casa]
    services.delete_label(casa)
    assert Task.objects.filter(pk=t.pk).exists()
    assert TaskLabel.objects.visible_to(eva, other).count() == 1


def test_filtros_del_tablero(home):
    household, ana, luis = home
    label = services.create_label(household, ana, "Jardín", "lime")
    task(household, ana, "de Luis", assignee=luis)
    task(household, ana, "sin nadie", labels=[label])
    assert [t.title for t in services.board(luis, household, "yo")["todo"]] == ["de Luis"]
    assert [t.title for t in services.board(luis, household, "nadie")["todo"]] == ["sin nadie"]
    assert [t.title for t in services.board(luis, household, "", label.pk)["todo"]] == ["sin nadie"]


def test_terminadas_limitadas(home):
    household, ana, _luis = home
    for n in range(services.DONE_LIMIT + 3):
        services.set_status(task(household, ana, f"t{n}"), ana, Task.Status.DONE)
    data = services.board(ana, household)
    assert len(data["done"]) == services.DONE_LIMIT
    assert data["done_total"] == services.DONE_LIMIT + 3


def test_estado_de_vencimiento(home):
    household, ana, _luis = home
    today = timezone.localdate()
    cases = {
        today - timedelta(days=1): "overdue",
        today: "today",
        today + timedelta(days=2): "soon",
        today + timedelta(days=10): "later",
    }
    for due, expected in cases.items():
        assert task(household, ana, due_date=due).due_state == expected
    done = task(household, ana, due_date=today - timedelta(days=1))
    services.set_status(done, ana, Task.Status.DONE)
    assert done.due_state == ""


def test_resumen_del_inicio(home):
    household, ana, luis = home
    today = timezone.localdate()
    task(household, ana, "vencida", due_date=today - timedelta(days=2))
    task(household, ana, "de Luis hoy", due_date=today, assignee=luis)
    task(household, ana, "mañana", due_date=today + timedelta(days=1))
    hecha = task(household, ana, "hecha", due_date=today)
    services.set_status(hecha, ana, Task.Status.DONE)

    ana_summary = services.dashboard_summary(ana, household)
    assert [t.title for t in ana_summary["due_tasks"]] == ["vencida"]
    luis_summary = services.dashboard_summary(luis, household)
    assert [t.title for t in luis_summary["due_tasks"]] == ["vencida", "de Luis hoy"]
    assert luis_summary["my_open_count"] == 1
