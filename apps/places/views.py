"""Vistas de sitios. Los datos parten de visible_to (services.places_for)."""

from urllib.parse import quote

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.core import social
from apps.core.mixins import HouseholdRequiredMixin
from apps.core.models import Membership

from . import services
from .forms import CommentForm, PlaceForm
from .models import CATEGORY_ICONS, Place, PlaceComment


def _colors(household) -> dict:
    return dict(Membership.objects.filter(household=household).values_list("user_id", "color"))


def map_url(place: Place) -> str:
    """Búsqueda en OpenStreetMap (solo se abre si la persona pulsa el enlace)."""
    query = place.location or place.name
    return f"https://www.openstreetmap.org/search?query={quote(query)}"


class PlaceMixin(HouseholdRequiredMixin):
    def get_place(self, pk):
        return get_object_or_404(
            services.places_for(self.request.user, self.request.household), pk=pk
        )

    def get_editable(self, pk):
        place = self.get_place(pk)
        if not place.can_edit(self.request.user):
            raise Http404
        return place


class PlaceListView(PlaceMixin, TemplateView):
    template_name = "places/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        get = self.request.GET
        status = get.get("estado") if get.get("estado") in services.FILTERS else "pendientes"
        category = get.get("categoria") if get.get("categoria") in Place.Category.values else ""
        query = get.get("q", "").strip()[:100]
        context.update(
            items=services.listing(
                self.request.user, self.request.household, status, category, query
            ),
            status=status,
            category=category,
            query=query,
            categories=Place.Category.choices,
            icons=CATEGORY_ICONS,
        )
        return context


class RandomView(PlaceMixin, View):
    """ "¿Dónde vamos?": un sitio pendiente al azar (HTMX devuelve solo la tarjeta)."""

    def get(self, request):
        category = request.GET.get("categoria", "")
        exclude = request.GET.get("anterior", "")
        place = services.pick_random(
            request.user, request.household, category, int(exclude) if exclude.isdigit() else None
        )
        context = {
            "place": place,
            "category": category,
            "categories": Place.Category.choices,
            "map_url": map_url(place) if place else "",
        }
        template = "places/partials/random.html" if request.htmx else "places/random.html"
        return render(request, template, context)


class PlaceCreateView(PlaceMixin, View):
    template_name = "places/form.html"

    def get(self, request):
        initial = {"category": request.GET.get("categoria") or Place.Category.RESTAURANT}
        return render(request, self.template_name, {"form": PlaceForm(initial=initial)})

    def post(self, request):
        form = PlaceForm(request.POST)
        if form.is_valid():
            try:
                place = services.create_place(request.household, request.user, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Sitio guardado."))
                return redirect("places:detail", pk=place.pk)
        return render(request, self.template_name, {"form": form}, status=400)


class PlaceEditView(PlaceMixin, View):
    template_name = "places/form.html"

    def get(self, request, pk):
        place = self.get_editable(pk)
        return render(
            request, self.template_name, {"form": PlaceForm(instance=place), "place": place}
        )

    def post(self, request, pk):
        place = self.get_editable(pk)
        form = PlaceForm(request.POST, instance=place)
        if form.is_valid():
            try:
                services.update_place(place, request.user, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("places:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "place": place}, status=400)


class PlaceDetailView(PlaceMixin, TemplateView):
    template_name = "places/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        place = self.get_place(self.kwargs["pk"])
        user = self.request.user
        context.update(social.rating_context(place, user))
        context.update(
            place=place,
            icon_name=CATEGORY_ICONS[place.category],
            map_url=map_url(place),
            can_edit=place.can_edit(user),
            can_delete=place.can_delete(user, self.request.membership),
            comments=place.comments.select_related("author"),
            colors=_colors(self.request.household),
            rate_url=reverse("places:rate", args=[place.pk]),
            target_id=f"rating-{place.pk}",
        )
        return context


class VisitedView(PlaceMixin, View):
    def post(self, request, pk):
        services.mark_visited(
            self.get_editable(pk), request.user, request.POST.get("visited") == "1"
        )
        return redirect("places:detail", pk=pk)


class ShareView(PlaceMixin, View):
    def post(self, request, pk):
        services.make_shared(self.get_place(pk), request.user)
        messages.success(request, _("Ahora lo ve todo el hogar."))
        return redirect("places:detail", pk=pk)


class DeleteView(PlaceMixin, View):
    def post(self, request, pk):
        services.delete_place(self.get_place(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        messages.success(request, _("Sitio borrado."))
        return redirect("places:list")


class RateView(PlaceMixin, View):
    def post(self, request, pk):
        place = self.get_place(pk)
        stars = request.POST.get("stars", "")
        try:
            services.rate(place, request.user, int(stars) if stars.isdigit() else 0)
        except ValidationError:
            return HttpResponse(status=400)
        if not request.htmx:
            return redirect("places:detail", pk=pk)
        context = social.rating_context(place, request.user)
        context.update(
            rate_url=reverse("places:rate", args=[pk]),
            target_id=f"rating-{pk}",
            colors=_colors(request.household),
        )
        return render(request, "partials/rating.html", context)


class CommentAddView(PlaceMixin, View):
    def post(self, request, pk):
        place = self.get_place(pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                services.add_comment(place, request.user, form.cleaned_data["body"])
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        return redirect(reverse("places:detail", args=[pk]) + "#comentarios")


class CommentDeleteView(PlaceMixin, View):
    def post(self, request, pk):
        visible = services.places_for(request.user, request.household)
        comment = get_object_or_404(PlaceComment, pk=pk, place__in=visible)
        social.delete_comment(comment, request.user)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect(reverse("places:detail", args=[comment.place_id]) + "#comentarios")
