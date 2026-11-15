"""Vistas de películas y series. Los datos parten de visible_to (services.titles_for)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View
from django.views.generic import TemplateView

from apps.core import social
from apps.core.mixins import HouseholdRequiredMixin
from apps.core.models import Membership

from . import services
from .forms import CommentForm, ProgressForm, TitleForm
from .models import Title, TitleComment

STATUS_TABS = [
    ("por-ver", gettext_lazy("Por ver")),
    ("viendo", gettext_lazy("Viendo")),
    ("vistas", gettext_lazy("Vistas")),
    ("abandonadas", gettext_lazy("Abandonadas")),
]


def _colors(household) -> dict:
    return dict(Membership.objects.filter(household=household).values_list("user_id", "color"))


class MediaMixin(HouseholdRequiredMixin):
    def get_item(self, pk):
        return get_object_or_404(
            services.titles_for(self.request.user, self.request.household), pk=pk
        )

    def get_editable(self, pk):
        item = self.get_item(pk)
        if not item.can_edit(self.request.user):
            raise Http404
        return item


class TitleListView(MediaMixin, TemplateView):
    template_name = "media/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        get = self.request.GET
        status = get.get("estado") if get.get("estado") in services.FILTERS else "por-ver"
        kind = get.get("tipo") if get.get("tipo") in Title.Kind.values else ""
        query = get.get("q", "").strip()[:100]
        user, household = self.request.user, self.request.household
        context.update(
            items=services.listing(user, household, status, kind, query),
            status=status,
            kind=kind,
            query=query,
            status_tabs=STATUS_TABS,
            kinds=Title.Kind.choices,
        )
        return context


class RandomView(MediaMixin, View):
    """ "¿Qué vemos?": algo por ver al azar (HTMX devuelve solo la tarjeta)."""

    def get(self, request):
        kind = request.GET.get("tipo", "")
        exclude = request.GET.get("anterior", "")
        item = services.pick_random(
            request.user, request.household, kind, int(exclude) if exclude.isdigit() else None
        )
        context = {"item": item, "kind": kind}
        template = "media/partials/random.html" if request.htmx else "media/random.html"
        return render(request, template, context)


class TitleCreateView(MediaMixin, View):
    template_name = "media/form.html"

    def get(self, request):
        initial = {"kind": request.GET.get("tipo") or Title.Kind.MOVIE}
        return render(request, self.template_name, {"form": TitleForm(initial=initial)})

    def post(self, request):
        form = TitleForm(request.POST)
        if form.is_valid():
            try:
                item = services.create_title(request.household, request.user, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Guardado."))
                return redirect("media:detail", pk=item.pk)
        return render(request, self.template_name, {"form": form}, status=400)


class TitleEditView(MediaMixin, View):
    template_name = "media/form.html"

    def get(self, request, pk):
        item = self.get_editable(pk)
        return render(request, self.template_name, {"form": TitleForm(instance=item), "item": item})

    def post(self, request, pk):
        item = self.get_editable(pk)
        form = TitleForm(request.POST, instance=item)
        if form.is_valid():
            try:
                services.update_title(item, request.user, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("media:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "item": item}, status=400)


class TitleDetailView(MediaMixin, TemplateView):
    template_name = "media/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_item(self.kwargs["pk"])
        user = self.request.user
        context.update(social.rating_context(item, user))
        progress = list(item.progress.select_related("user")) if item.is_series else []
        context.update(
            item=item,
            can_edit=item.can_edit(user),
            can_delete=item.can_delete(user, self.request.membership),
            statuses=Title.Status.choices,
            comments=item.comments.select_related("author"),
            colors=_colors(self.request.household),
            my_progress=next((p for p in progress if p.user_id == user.pk), None),
            others_progress=[p for p in progress if p.user_id != user.pk],
            rate_url=reverse("media:rate", args=[item.pk]),
            target_id=f"rating-{item.pk}",
        )
        return context


class StatusView(MediaMixin, View):
    def post(self, request, pk):
        try:
            services.set_status(self.get_editable(pk), request.user, request.POST.get("status", ""))
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        return redirect("media:detail", pk=pk)


class ShareView(MediaMixin, View):
    def post(self, request, pk):
        services.make_shared(self.get_item(pk), request.user)
        messages.success(request, _("Ahora la ve todo el hogar."))
        return redirect("media:detail", pk=pk)


class DeleteView(MediaMixin, View):
    def post(self, request, pk):
        services.delete_title(self.get_item(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        messages.success(request, _("Borrado."))
        return redirect("media:list")


class RateView(MediaMixin, View):
    def post(self, request, pk):
        item = self.get_item(pk)
        stars = request.POST.get("stars", "")
        try:
            services.rate(item, request.user, int(stars) if stars.isdigit() else 0)
        except ValidationError:
            return HttpResponse(status=400)
        if not request.htmx:
            return redirect("media:detail", pk=pk)
        context = social.rating_context(item, request.user)
        context.update(
            rate_url=reverse("media:rate", args=[pk]),
            target_id=f"rating-{pk}",
            colors=_colors(request.household),
        )
        return render(request, "partials/rating.html", context)


class ProgressView(MediaMixin, View):
    def post(self, request, pk):
        item = self.get_item(pk)
        try:
            if request.POST.get("next") == "1":
                services.next_episode(item, request.user)
            else:
                form = ProgressForm(request.POST)
                if not form.is_valid():
                    raise ValidationError(_("Temporada o episodio no válidos."))
                services.set_progress(
                    item, request.user, form.cleaned_data["season"], form.cleaned_data["episode"]
                )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        return redirect(reverse("media:detail", args=[pk]) + "#progreso")


class CommentAddView(MediaMixin, View):
    def post(self, request, pk):
        item = self.get_item(pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                services.add_comment(item, request.user, form.cleaned_data["body"])
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        return redirect(reverse("media:detail", args=[pk]) + "#comentarios")


class CommentDeleteView(MediaMixin, View):
    def post(self, request, pk):
        visible = services.titles_for(request.user, request.household)
        comment = get_object_or_404(TitleComment, pk=pk, title__in=visible)
        social.delete_comment(comment, request.user)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect(reverse("media:detail", args=[comment.title_id]) + "#comentarios")
