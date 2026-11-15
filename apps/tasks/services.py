"""Lógica de negocio de tareas: quién puede editar, mover, asignar y borrar."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Min, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import recurrence
from apps.core.models import Membership, Visibility

from .models import Subtask, Task, TaskComment, TaskLabel

DONE_LIMIT = 20  # tareas terminadas que se muestran en el tablero


def tasks_for(user, household):
    return Task.objects.visible_to(user, household).select_related("assignee", "owner")


def labels_for(user, household):
    return TaskLabel.objects.visible_to(user, household)


def _require_edit(task: Task, user):
    if not task.can_edit(user):
        raise PermissionDenied


def _check_assignee(household, owner, visibility, assignee):
    """El responsable debe ser miembro del hogar. Una tarea personal solo puede ser de
    su dueño (nadie más la vería)."""
    if assignee is None:
        return
    if not Membership.objects.filter(household=household, user=assignee).exists():
        raise ValidationError(_("El responsable debe ser miembro del hogar."))
    if visibility == Visibility.PRIVATE and assignee.pk != owner.pk:
        raise ValidationError(_("Una tarea personal solo puede asignarse a ti."))


def _top_position(household, status) -> int:
    lowest = Task.objects.filter(household=household, status=status).aggregate(m=Min("position"))
    return (lowest["m"] or 0) - 1


def _apply_status(task: Task, status: str):
    if status not in Task.Status.values:
        raise ValidationError(_("Estado no válido."))
    if status == Task.Status.DONE and task.status != Task.Status.DONE:
        task.completed_at = timezone.now()
    elif status != Task.Status.DONE:
        task.completed_at = None
    task.status = status


def _check_recurrence(data):
    rule = data.get("recurrence_rule")
    if not rule:
        return
    if not recurrence.is_valid(rule):
        raise ValidationError(_("La repetición no es válida."))
    if not data.get("due_date"):
        raise ValidationError(_("Una tarea que se repite necesita fecha límite."))


def spawn_next(task: Task) -> Task | None:
    """Si la tarea se repite, crea la siguiente (pendiente) con la próxima fecha límite.

    La fecha siguiente es la primera de la serie posterior a hoy, para que una tarea
    terminada con retraso no genere otra ya vencida. Se hace una sola vez por tarea.
    """
    if not task.recurrence_rule or not task.due_date or task.recurrence_spawned:
        return None
    today = timezone.localdate()
    following = recurrence.next_date(task.recurrence_rule, task.due_date)
    while following and following <= today:
        following = recurrence.next_date(task.recurrence_rule, following)
    task.recurrence_spawned = True
    task.save(update_fields=["recurrence_spawned"])
    if following is None:
        return None  # la serie ha terminado (fecha "hasta")
    new = Task.objects.create(
        household=task.household,
        owner=task.owner,
        visibility=task.visibility,
        title=task.title,
        description=task.description,
        assignee=task.assignee,
        priority=task.priority,
        due_date=following,
        recurrence_rule=task.recurrence_rule,
        position=_top_position(task.household, Task.Status.TODO),
    )
    new.labels.set(task.labels.all())
    for sub in task.subtasks.all():
        Subtask.objects.create(task=new, title=sub.title, position=sub.position)
    return new


def create_task(household, user, title, labels=(), **data) -> Task:
    title = " ".join((title or "").split())
    if not title:
        raise ValidationError(_("Escribe el título de la tarea."))
    visibility = data.get("visibility", Visibility.SHARED)
    _check_assignee(household, user, visibility, data.get("assignee"))
    _check_recurrence(data)
    status = data.pop("status", Task.Status.TODO)
    task = Task(household=household, owner=user, title=title, **data)
    _apply_status(task, status)
    task.position = _top_position(household, task.status)
    task.save()
    if labels:
        task.labels.set([lb for lb in labels if lb.household_id == household.pk])
    if task.is_done:
        spawn_next(task)
    return task


def update_task(task: Task, user, labels=None, **data) -> Task:
    _require_edit(task, user)
    data.pop("visibility", None)  # se cambia con make_shared
    if "title" in data:
        data["title"] = " ".join(data["title"].split())
        if not data["title"]:
            raise ValidationError(_("Escribe el título de la tarea."))
    _check_assignee(task.household, task.owner, task.visibility, data.get("assignee"))
    _check_recurrence({"due_date": task.due_date, **data})
    for field, value in data.items():
        setattr(task, field, value)
    task.save()
    if labels is not None:
        task.labels.set([lb for lb in labels if lb.household_id == task.household_id])
    return task


def make_shared(task: Task, user) -> Task:
    if task.owner_id != user.pk:
        raise PermissionDenied
    task.visibility = Visibility.SHARED
    task.save(update_fields=["visibility", "updated_at"])
    return task


def set_status(task: Task, user, status: str) -> Task:
    """Cambia de columna (botones "Empezar", "Terminar", "Reabrir"). Va arriba del todo."""
    _require_edit(task, user)
    if task.status != status:
        _apply_status(task, status)
        task.position = _top_position(task.household, status)
        task.save(update_fields=["status", "completed_at", "position", "updated_at"])
        if task.is_done:
            spawn_next(task)
    return task


@transaction.atomic
def move_task(task: Task, user, status: str, order: list[int]) -> Task:
    """Arrastrar y soltar: deja la tarea en `status` y reordena esa columna según `order`
    (ids en el orden en que se ven). Solo se reordenan las tareas que la persona ve."""
    _require_edit(task, user)
    _apply_status(task, status)
    task.save(update_fields=["status", "completed_at", "updated_at"])
    if task.is_done:
        spawn_next(task)
    column = {
        t.pk: t
        for t in tasks_for(user, task.household).filter(status=status, pk__in=order)
        if t.can_edit(user)
    }
    position = 0
    for pk in order:
        if pk in column:
            Task.objects.filter(pk=pk).update(position=position)
            position += 1
    return task


def delete_task(task: Task, user, membership) -> None:
    if not task.can_delete(user, membership):
        raise PermissionDenied
    task.delete()


def board(user, household, assignee_filter="", label_id=None) -> dict:
    """Columnas del tablero ya filtradas. Devuelve {status: [tareas]} y recuentos."""
    # order_by explícito: Django no aplica Meta.ordering en consultas con recuentos.
    qs = (
        tasks_for(user, household)
        .with_counts()
        .prefetch_related("labels")
        .order_by("position", "created_at")
    )
    if assignee_filter == "yo":
        qs = qs.filter(assignee=user)
    elif assignee_filter == "nadie":
        qs = qs.filter(assignee__isnull=True)
    if label_id:
        qs = qs.filter(labels__id=label_id)
    done = qs.filter(status=Task.Status.DONE)
    return {
        "todo": list(qs.filter(status=Task.Status.TODO)),
        "doing": list(qs.filter(status=Task.Status.DOING)),
        "done": list(done.order_by("-completed_at")[:DONE_LIMIT]),
        "done_total": done.count(),
    }


# --- Subtareas ----------------------------------------------------------------------------


def add_subtask(task: Task, user, title: str) -> Subtask:
    _require_edit(task, user)
    title = " ".join((title or "").split())
    if not title:
        raise ValidationError(_("Escribe la subtarea."))
    last = task.subtasks.aggregate(m=Max("position"))["m"]
    return Subtask.objects.create(task=task, title=title[:200], position=(last or 0) + 1)


def toggle_subtask(subtask: Subtask, user) -> Subtask:
    _require_edit(subtask.task, user)
    subtask.is_done = not subtask.is_done
    subtask.save(update_fields=["is_done"])
    return subtask


def delete_subtask(subtask: Subtask, user) -> None:
    _require_edit(subtask.task, user)
    subtask.delete()


# --- Comentarios --------------------------------------------------------------------------


def add_comment(task: Task, user, body: str) -> TaskComment:
    body = (body or "").strip()
    if not body:
        raise ValidationError(_("Escribe un comentario."))
    return TaskComment.objects.create(task=task, author=user, body=body[:2000])


def delete_comment(comment: TaskComment, user) -> None:
    if comment.author_id != user.pk:
        raise PermissionDenied
    comment.delete()


# --- Etiquetas ----------------------------------------------------------------------------


def create_label(household, user, name: str, color: str) -> TaskLabel:
    name = " ".join((name or "").split())
    if not name:
        raise ValidationError(_("Escribe el nombre de la etiqueta."))
    if TaskLabel.objects.filter(household=household, name__iexact=name).exists():
        raise ValidationError(_("Ya existe una etiqueta con ese nombre."))
    return TaskLabel.objects.create(household=household, owner=user, name=name[:40], color=color)


def delete_label(label: TaskLabel) -> None:
    """Cualquier miembro puede borrar etiquetas (son comunes). Las tareas no se borran."""
    label.delete()


# --- Dashboard ----------------------------------------------------------------------------


def dashboard_summary(user, household) -> dict:
    """Tareas sin terminar que vencen hoy o ya han vencido (mías o sin responsable)."""
    today = timezone.localdate()
    open_tasks = tasks_for(user, household).exclude(status=Task.Status.DONE)
    mine = open_tasks.filter(Q(assignee=user) | Q(assignee__isnull=True))
    due = list(mine.filter(due_date__lte=today).order_by("due_date", "position")[:5])
    return {
        "due_tasks": due,
        "my_open_count": open_tasks.filter(assignee=user).count(),
    }
