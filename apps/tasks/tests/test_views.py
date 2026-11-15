"""Vistas de tareas: funcionamiento y autorización (otro miembro, otro hogar, anónimo)."""

import pytest
from django.urls import reverse

from apps.core.models import Visibility
from apps.tasks import services
from apps.tasks.models import Subtask, Task, TaskComment, TaskLabel

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}
UNDO = {"HTTP_X_UNDO_COMMIT": "1"}


@pytest.fixture
def data(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    shared = services.create_task(household, ana, "Fregar")
    private = services.create_task(household, ana, "Regalo", visibility=Visibility.PRIVATE)
    foreign = services.create_task(other, eva, "Podar")
    return {
        "household": household,
        "ana": ana,
        "luis": luis,
        "eva": eva,
        "shared": shared,
        "private": private,
        "foreign": foreign,
        "private_sub": services.add_subtask(private, ana, "Envolver"),
        "foreign_sub": services.add_subtask(foreign, eva, "Tijeras"),
        "foreign_label": services.create_label(other, eva, "Jardín", "lime"),
    }


PAGES = ["tasks:board", "tasks:create", "tasks:labels"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert reverse("core:login") in response.url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_anonimo_no_crea(client, data):
    client.post(reverse("tasks:quick_add"), {"title": "x"})
    assert not Task.objects.filter(title="x").exists()


TASK_GET = ["tasks:detail", "tasks:edit"]
TASK_POST = [
    ("tasks:edit", {"title": "Hackeada", "priority": "low"}),
    ("tasks:move", {"status": "done", "order": ""}),
    ("tasks:status", {"status": "done"}),
    ("tasks:share", {}),
    ("tasks:delete", {}),
    ("tasks:subtask_add", {"title": "intrusa"}),
    ("tasks:comment_add", {"body": "hola"}),
]


@pytest.mark.parametrize("name", TASK_GET)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_tarea_ajena_da_404_al_verla(login_as, data, name, who, target):
    response = login_as(data[who]).get(reverse(name, args=[data[target].pk]))
    assert response.status_code == 404


@pytest.mark.parametrize(("name", "payload"), TASK_POST)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_tarea_ajena_da_404_al_modificarla(login_as, data, name, payload, who, target):
    t = data[target]
    before = (t.title, t.status, t.visibility)
    response = login_as(data[who]).post(reverse(name, args=[t.pk]), payload, **HTMX)
    assert response.status_code == 404
    t.refresh_from_db()
    assert (t.title, t.status, t.visibility) == before
    assert t.subtasks.count() == 1
    assert not TaskComment.objects.filter(task=t).exists()


@pytest.mark.parametrize("name", ["tasks:subtask_toggle", "tasks:subtask_delete"])
@pytest.mark.parametrize(("who", "target"), [("luis", "private_sub"), ("ana", "foreign_sub")])
def test_subtarea_ajena_da_404(login_as, data, name, who, target):
    sub = data[target]
    response = login_as(data[who]).post(reverse(name, args=[sub.pk]), **UNDO)
    assert response.status_code == 404
    sub.refresh_from_db()
    assert not sub.is_done


def test_etiqueta_de_otro_hogar_da_404(login_as, data):
    label = data["foreign_label"]
    response = login_as(data["ana"]).post(reverse("tasks:label_delete", args=[label.pk]), **UNDO)
    assert response.status_code == 404
    assert TaskLabel.objects.filter(pk=label.pk).exists()


def test_etiqueta_de_otro_hogar_no_se_puede_asignar(login_as, data):
    response = login_as(data["ana"]).post(
        reverse("tasks:create"),
        {
            "title": "Con etiqueta ajena",
            "visibility": "shared",
            "priority": "medium",
            "status": "todo",
            "labels": [data["foreign_label"].pk],
        },
    )
    assert response.status_code == 400
    assert not Task.objects.filter(title="Con etiqueta ajena").exists()


def test_no_se_ve_lo_ajeno_en_el_tablero(login_as, data):
    html = login_as(data["luis"]).get(reverse("tasks:board")).content.decode()
    assert "Fregar" in html
    assert "Regalo" not in html and "Podar" not in html


def test_miembro_no_admin_no_borra_lo_ajeno(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("tasks:delete", args=[data["shared"].pk]), **UNDO
    )
    assert response.status_code == 403
    assert Task.objects.filter(pk=data["shared"].pk).exists()


# --- Funcionamiento -----------------------------------------------------------------------


def test_alta_rapida_devuelve_el_tablero(login_as, data):
    response = login_as(data["luis"]).post(reverse("tasks:quick_add"), {"title": "Tender"}, **HTMX)
    html = response.content.decode()
    assert response.status_code == 200
    assert "Tender" in html and 'data-status="todo"' in html and "<html" not in html
    assert Task.objects.get(title="Tender").owner == data["luis"]


def test_alta_rapida_sin_javascript_conserva_filtros(login_as, data):
    response = login_as(data["luis"]).post(reverse("tasks:quick_add") + "?de=yo", {"title": "X"})
    assert response.status_code == 302
    assert response.url == reverse("tasks:board") + "?de=yo"


def test_arrastrar_a_otra_columna(login_as, data):
    t = data["shared"]
    response = login_as(data["luis"]).post(
        reverse("tasks:move", args=[t.pk]), {"status": "doing", "order": f"{t.pk},abc"}, **HTMX
    )
    assert response.status_code == 200
    t.refresh_from_db()
    assert t.status == Task.Status.DOING


def test_mover_a_estado_no_valido(login_as, data):
    t = data["shared"]
    response = login_as(data["luis"]).post(
        reverse("tasks:move", args=[t.pk]), {"status": "x", "order": ""}, **HTMX
    )
    assert response.status_code == 400


def test_botones_de_estado(login_as, data):
    t = data["shared"]
    client = login_as(data["luis"])
    client.post(reverse("tasks:status", args=[t.pk]), {"status": "done"}, **HTMX)
    t.refresh_from_db()
    assert t.status == Task.Status.DONE and t.completed_at
    response = client.post(
        reverse("tasks:status", args=[t.pk]), {"status": "todo", "next": "detail"}
    )
    assert response.url == reverse("tasks:detail", args=[t.pk])


def test_crear_tarea_completa(login_as, data):
    label = services.create_label(data["household"], data["ana"], "Cocina", "violet")
    response = login_as(data["luis"]).post(
        reverse("tasks:create"),
        {
            "title": "Limpiar horno",
            "visibility": "shared",
            "assignee": data["ana"].pk,
            "due_date": "2026-12-01",
            "priority": "high",
            "status": "doing",
            "description": "Con bicarbonato",
            "labels": [label.pk],
        },
    )
    t = Task.objects.get(title="Limpiar horno")
    assert response.status_code == 302
    assert (t.owner, t.assignee, t.status, t.priority) == (
        data["luis"],
        data["ana"],
        "doing",
        "high",
    )
    assert str(t.due_date) == "2026-12-01"
    assert list(t.labels.all()) == [label]


def test_crear_personal_asignada_a_otro_falla(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("tasks:create"),
        {
            "title": "Secreto",
            "visibility": "private",
            "assignee": data["ana"].pk,
            "priority": "medium",
            "status": "todo",
        },
    )
    assert response.status_code == 400
    assert not Task.objects.filter(title="Secreto").exists()


def test_responsable_de_otro_hogar_no_se_acepta(login_as, data):
    response = login_as(data["ana"]).post(
        reverse("tasks:create"),
        {
            "title": "Para Eva",
            "visibility": "shared",
            "assignee": data["eva"].pk,
            "priority": "medium",
            "status": "todo",
        },
    )
    assert response.status_code == 400


def test_editar_tarea(login_as, data):
    t = data["shared"]
    response = login_as(data["luis"]).post(
        reverse("tasks:edit", args=[t.pk]),
        {"title": "Fregar platos", "priority": "low", "assignee": data["luis"].pk},
    )
    assert response.status_code == 302
    t.refresh_from_db()
    assert t.title == "Fregar platos" and t.assignee == data["luis"]


def test_detalle_muestra_subtareas_y_comentarios(login_as, data):
    t = data["shared"]
    services.add_subtask(t, data["ana"], "Secar")
    services.add_comment(t, data["ana"], "Hay jabón nuevo")
    html = login_as(data["luis"]).get(reverse("tasks:detail", args=[t.pk])).content.decode()
    assert "Secar" in html and "Hay jabón nuevo" in html
    assert reverse("tasks:delete", args=[t.pk]) not in html  # Luis no puede borrarla


def test_subtareas_con_htmx(login_as, data):
    t = data["shared"]
    client = login_as(data["luis"])
    response = client.post(reverse("tasks:subtask_add", args=[t.pk]), {"title": "Secar"}, **HTMX)
    assert response.status_code == 200 and "Secar" in response.content.decode()
    sub = Subtask.objects.get(task=t)
    client.post(reverse("tasks:subtask_toggle", args=[sub.pk]), **HTMX)
    sub.refresh_from_db()
    assert sub.is_done
    assert client.post(reverse("tasks:subtask_delete", args=[sub.pk]), **UNDO).status_code == 204
    assert not Subtask.objects.filter(pk=sub.pk).exists()


def test_comentar_y_borrar(login_as, data):
    t = data["shared"]
    client = login_as(data["luis"])
    client.post(reverse("tasks:comment_add", args=[t.pk]), {"body": "Hecho a medias"})
    comment = TaskComment.objects.get(task=t)
    other = login_as(data["ana"]).post(reverse("tasks:comment_delete", args=[comment.pk]), **UNDO)
    assert other.status_code == 403
    client = login_as(data["luis"])
    assert (
        client.post(reverse("tasks:comment_delete", args=[comment.pk]), **UNDO).status_code == 204
    )


def test_crear_y_borrar_etiqueta(login_as, data):
    client = login_as(data["luis"])
    assert client.post(reverse("tasks:labels"), {"name": "Baño", "color": "sky"}).status_code == 302
    dup = client.post(reverse("tasks:labels"), {"name": "baño", "color": "sky"})
    assert dup.status_code == 400
    label = TaskLabel.objects.get(name="Baño")
    assert client.post(reverse("tasks:label_delete", args=[label.pk]), **UNDO).status_code == 204


def test_duenno_borra_su_tarea(login_as, data):
    t = data["private"]
    response = login_as(data["ana"]).post(reverse("tasks:delete", args=[t.pk]), **UNDO)
    assert response.status_code == 204
    assert not Task.objects.filter(pk=t.pk).exists()


def test_inicio_muestra_tareas_para_hoy(login_as, data):
    from django.utils import timezone

    t = data["shared"]
    t.due_date = timezone.localdate()
    t.save()
    html = login_as(data["luis"]).get(reverse("core:home")).content.decode()
    assert "Para hoy" in html and "Fregar" in html
