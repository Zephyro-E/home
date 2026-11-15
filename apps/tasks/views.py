"""Vistas de tareas. Los datos parten siempre de visible_to (services.tasks_for): lo que no
se puede ver da 404. Las reglas viven en services.py."""

from contextlib import suppress

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import HouseholdRequiredMixin
from apps.core.models import MEMBER_COLORS, Membership

from . import services
from .forms import CommentForm, LabelForm, QuickTaskForm, SubtaskForm, TaskForm
from .models import Subtask, Task, TaskComment


def _member_colors(household) -> dict:
    return dict(Membership.objects.filter(household=household).values_list("user_id", "color"))


def _undo_commit(request) -> bool:
    return bool(request.headers.get("X-Undo-Commit"))


class TaskMixin(HouseholdRequiredMixin):
    def get_task(self, pk):
        return get_object_or_404(
            services.tasks_for(self.request.user, self.request.household), pk=pk
        )

    def get_editable(self, pk):
        task = self.get_task(pk)
        if not task.can_edit(self.request.user):
            raise Http404
        return task


# --- Tablero ------------------------------------------------------------------------------


class BoardMixin(TaskMixin):
    def filters(self):
        assignee = self.request.GET.get("de", "")
        assignee = assignee if assignee in {"yo", "nadie"} else ""
        label = self.request.GET.get("etiqueta", "")
        label_id = int(label) if label.isdigit() else None
        return assignee, label_id

    def board_context(self):
        user, household = self.request.user, self.request.household
        assignee, label_id = self.filters()
        data = services.board(user, household, assignee, label_id)
        columns = [
            ("todo", _("Pendiente"), data["todo"], len(data["todo"])),
            ("doing", _("En curso"), data["doing"], len(data["doing"])),
            ("done", _("Terminada"), data["done"], data["done_total"]),
        ]
        return {
            "columns": columns,
            "done_hidden": data["done_total"] - len(data["done"]),
            "colors": _member_colors(household),
            "assignee_filter": assignee,
            "label_filter": label_id,
            "labels": services.labels_for(user, household),
            "query": self.request.GET.urlencode(),
        }

    def render_board(self):
        if self.request.htmx:
            return render(self.request, "tasks/partials/board.html", self.board_context())
        url = reverse("tasks:board")
        query = self.request.GET.urlencode()
        return redirect(f"{url}?{query}" if query else url)


class BoardView(BoardMixin, TemplateView):
    template_name = "tasks/board.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.board_context())
        return context


class QuickAddView(BoardMixin, View):
    def post(self, request):
        form = QuickTaskForm(request.POST)
        if form.is_valid():
            # Si el título queda vacío tras limpiar espacios, no se crea nada.
            with suppress(ValidationError):
                services.create_task(request.household, request.user, form.cleaned_data["title"])
        return self.render_board()


class MoveView(BoardMixin, View):
    """Arrastrar y soltar: nueva columna y orden de esa columna."""

    def post(self, request, pk):
        task = self.get_editable(pk)
        order = [int(v) for v in request.POST.get("order", "").split(",") if v.isdigit()]
        try:
            services.move_task(task, request.user, request.POST.get("status", ""), order)
        except ValidationError:
            return HttpResponse(status=400)
        return self.render_board()


class StatusView(BoardMixin, View):
    """Botones Empezar / Terminar / Reabrir (tablero) y botones de estado (detalle)."""

    def post(self, request, pk):
        task = self.get_editable(pk)
        try:
            services.set_status(task, request.user, request.POST.get("status", ""))
        except ValidationError:
            return HttpResponse(status=400)
        if request.POST.get("next") == "detail":
            return redirect("tasks:detail", pk=pk)
        return self.render_board()


# --- Crear, ver, editar, borrar -----------------------------------------------------------


class TaskCreateView(TaskMixin, View):
    template_name = "tasks/task_form.html"

    def form(self, data=None, **kwargs):
        return TaskForm(data, household=self.request.household, user=self.request.user, **kwargs)

    def get(self, request):
        initial = {"assignee": request.user} if request.GET.get("de") == "yo" else {}
        return render(request, self.template_name, {"form": self.form(initial=initial)})

    def post(self, request):
        form = self.form(request.POST)
        if form.is_valid():
            try:
                task = services.create_task(
                    request.household,
                    request.user,
                    labels=form.cleaned_data["labels"],
                    **form.task_data(),
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Tarea creada."))
                return redirect("tasks:detail", pk=task.pk)
        return render(request, self.template_name, {"form": form}, status=400)


class TaskEditView(TaskMixin, View):
    template_name = "tasks/task_form.html"

    def form(self, task, data=None):
        return TaskForm(
            data, instance=task, household=self.request.household, user=self.request.user
        )

    def get(self, request, pk):
        task = self.get_editable(pk)
        return render(request, self.template_name, {"form": self.form(task), "task": task})

    def post(self, request, pk):
        task = self.get_editable(pk)
        form = self.form(task, request.POST)
        if form.is_valid():
            try:
                services.update_task(
                    task, request.user, labels=form.cleaned_data["labels"], **form.task_data()
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("tasks:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "task": task}, status=400)


class TaskDetailView(TaskMixin, TemplateView):
    template_name = "tasks/task_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_task(self.kwargs["pk"])
        user = self.request.user
        context.update(
            task=task,
            can_edit=task.can_edit(user),
            can_delete=task.can_delete(user, self.request.membership),
            statuses=Task.Status.choices,
            subtasks=task.subtasks.all(),
            comments=task.comments.select_related("author"),
            colors=_member_colors(self.request.household),
        )
        return context


class TaskShareView(TaskMixin, View):
    def post(self, request, pk):
        services.make_shared(self.get_task(pk), request.user)
        messages.success(request, _("Ahora la tarea es del hogar: el resto ya la ve."))
        return redirect("tasks:detail", pk=pk)


class TaskDeleteView(TaskMixin, View):
    def post(self, request, pk):
        services.delete_task(self.get_task(pk), request.user, request.membership)
        if _undo_commit(request):
            return HttpResponse(status=204)
        messages.success(request, _("Tarea borrada."))
        return redirect("tasks:board")


# --- Subtareas ----------------------------------------------------------------------------


class SubtaskMixin(TaskMixin):
    def render_subtasks(self, task, refocus=False):
        if self.request.htmx:
            context = {
                "task": task,
                "subtasks": task.subtasks.all(),
                "can_edit": True,
                "refocus": refocus,  # tras añadir, el cursor vuelve al campo
            }
            return render(self.request, "tasks/partials/subtasks.html", context)
        return redirect(reverse("tasks:detail", args=[task.pk]) + "#subtareas")

    def get_subtask(self, pk):
        visible = services.tasks_for(self.request.user, self.request.household)
        subtask = get_object_or_404(Subtask.objects.select_related("task"), pk=pk, task__in=visible)
        if not subtask.task.can_edit(self.request.user):
            raise Http404
        return subtask


class SubtaskAddView(SubtaskMixin, View):
    def post(self, request, pk):
        task = self.get_editable(pk)
        form = SubtaskForm(request.POST)
        if form.is_valid():
            with suppress(ValidationError):
                services.add_subtask(task, request.user, form.cleaned_data["title"])
        return self.render_subtasks(task, refocus=True)


class SubtaskToggleView(SubtaskMixin, View):
    def post(self, request, pk):
        subtask = self.get_subtask(pk)
        services.toggle_subtask(subtask, request.user)
        return self.render_subtasks(subtask.task)


class SubtaskDeleteView(SubtaskMixin, View):
    def post(self, request, pk):
        subtask = self.get_subtask(pk)
        services.delete_subtask(subtask, request.user)
        if _undo_commit(request):
            return HttpResponse(status=204)
        return self.render_subtasks(subtask.task)


# --- Comentarios --------------------------------------------------------------------------


class CommentAddView(TaskMixin, View):
    def post(self, request, pk):
        task = self.get_task(pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                services.add_comment(task, request.user, form.cleaned_data["body"])
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        return redirect(reverse("tasks:detail", args=[pk]) + "#comentarios")


class CommentDeleteView(TaskMixin, View):
    def post(self, request, pk):
        visible = services.tasks_for(request.user, request.household)
        comment = get_object_or_404(TaskComment, pk=pk, task__in=visible)
        services.delete_comment(comment, request.user)
        if _undo_commit(request):
            return HttpResponse(status=204)
        return redirect(reverse("tasks:detail", args=[comment.task_id]) + "#comentarios")


# --- Etiquetas ----------------------------------------------------------------------------


class LabelsView(HouseholdRequiredMixin, View):
    template_name = "tasks/labels.html"

    def render_page(self, form, status=200):
        labels = services.labels_for(self.request.user, self.request.household)
        context = {"form": form, "labels": labels, "colors": MEMBER_COLORS}
        return render(self.request, self.template_name, context, status=status)

    def get(self, request):
        return self.render_page(LabelForm(initial={"color": MEMBER_COLORS[0]}))

    def post(self, request):
        form = LabelForm(request.POST)
        if form.is_valid():
            try:
                services.create_label(
                    request.household,
                    request.user,
                    form.cleaned_data["name"],
                    form.cleaned_data["color"],
                )
            except ValidationError as error:
                form.add_error("name", error)
            else:
                messages.success(request, _("Etiqueta creada."))
                return redirect("tasks:labels")
        return self.render_page(form, status=400)


class LabelDeleteView(HouseholdRequiredMixin, View):
    def post(self, request, pk):
        label = get_object_or_404(services.labels_for(request.user, request.household), pk=pk)
        services.delete_label(label)
        if _undo_commit(request):
            return HttpResponse(status=204)
        return redirect("tasks:labels")
