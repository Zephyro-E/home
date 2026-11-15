"""Vistas de compras. Todos los datos parten de visible_to (vía services.*_for): lo que no
se puede ver da 404. Las reglas de edición viven en services.py."""

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
from apps.core.models import Membership, Visibility

from . import services
from .forms import CommentForm, GroceryForm, WishForm
from .models import WishComment, WishItem, WishVote


def _ids(values) -> list[int]:
    return [int(v) for v in values if str(v).isdigit()]


# --- Lista de la compra -------------------------------------------------------------------


class GroceryMixin(HouseholdRequiredMixin):
    def grocery_context(self):
        items = list(services.grocery_for(self.request.user, self.request.household))
        return {
            "pending": [i for i in items if not i.is_checked],
            "checked": [i for i in items if i.is_checked],
        }

    def render_list(self):
        """Con HTMX devuelve solo la lista; sin JavaScript, vuelve a la página."""
        if self.request.htmx:
            return render(
                self.request, "shopping/partials/grocery_list.html", self.grocery_context()
            )
        return redirect("shopping:list")


class GroceryListView(GroceryMixin, TemplateView):
    template_name = "shopping/grocery.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.grocery_context())
        context["form"] = GroceryForm()
        return context


class GroceryAddView(GroceryMixin, View):
    def post(self, request):
        form = GroceryForm(request.POST)
        if form.is_valid():
            # Si el nombre queda vacío tras limpiar espacios, no se añade nada.
            with suppress(ValidationError):
                services.add_grocery(
                    request.household,
                    request.user,
                    form.cleaned_data["name"],
                    form.cleaned_data["quantity"],
                )
        return self.render_list()


class GroceryToggleView(GroceryMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(services.grocery_for(request.user, request.household), pk=pk)
        services.set_grocery_checked(item, request.user, request.POST.get("checked") == "1")
        return self.render_list()


class GroceryDeleteView(GroceryMixin, View):
    """Borrado definitivo, llamado al expirar el aviso de "Deshacer" (ADR-010)."""

    def post(self, request):
        services.delete_groceries(request.user, request.household, _ids(request.POST.getlist("id")))
        if request.htmx or request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect("shopping:list")


# --- Deseos -------------------------------------------------------------------------------

STATUS_FILTERS = {
    "activos": WishItem.ACTIVE_STATUSES,
    "comprados": (WishItem.Status.BOUGHT,),
    "descartados": (WishItem.Status.DISCARDED,),
}


class WishMixin(HouseholdRequiredMixin):
    def get_wish(self, pk, stats=False):
        qs = services.wishes_for(self.request.user, self.request.household)
        if stats:
            qs = qs.with_stats()
        return get_object_or_404(qs, pk=pk)

    def my_votes(self, items) -> dict[int, int]:
        rows = WishVote.objects.filter(
            user=self.request.user, item__in=[i.pk for i in items]
        ).values_list("item_id", "value")
        return dict(rows)


class WishListView(WishMixin, TemplateView):
    template_name = "shopping/wishes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, household = self.request.user, self.request.household
        view = "mios" if self.request.GET.get("ver") == "mios" else "comunes"
        status = self.request.GET.get("estado")
        status = status if status in STATUS_FILTERS else "activos"

        base = services.wishes_for(user, household)
        shared = base.filter(visibility=Visibility.SHARED)
        mine = base.filter(visibility=Visibility.PRIVATE, owner=user)
        qs = mine if view == "mios" else shared
        items = list(
            qs.filter(status__in=STATUS_FILTERS[status])
            .with_stats()
            .order_by("-score", "-created_at")
        )
        votes = self.my_votes(items)
        for item in items:
            item.my_vote = votes.get(item.pk)

        context.update(
            view=view,
            status=status,
            items=items,
            shared_count=shared.filter(status__in=WishItem.ACTIVE_STATUSES).count(),
            mine_count=mine.filter(status__in=WishItem.ACTIVE_STATUSES).count(),
            status_filters=[
                ("activos", _("Activos")),
                ("comprados", _("Comprados")),
                ("descartados", _("Descartados")),
            ],
        )
        return context


class WishCreateView(WishMixin, View):
    template_name = "shopping/wish_form.html"

    def get(self, request):
        mine = request.GET.get("ver") == "mios"
        initial = {"visibility": Visibility.PRIVATE if mine else Visibility.SHARED}
        return render(request, self.template_name, {"form": WishForm(initial=initial)})

    def post(self, request):
        form = WishForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)
        item = services.create_wish(request.household, request.user, **form.wish_data())
        messages.success(request, _("Deseo guardado."))
        return redirect("shopping:wish_detail", pk=item.pk)


class WishEditView(WishMixin, View):
    template_name = "shopping/wish_form.html"

    def get_editable(self, pk):
        item = self.get_wish(pk)
        if not item.can_edit(self.request.user):
            raise Http404  # lo ve pero no puede editarlo (privado ajeno no llega a verse)
        return item

    def get(self, request, pk):
        item = self.get_editable(pk)
        return render(request, self.template_name, {"form": WishForm(instance=item), "item": item})

    def post(self, request, pk):
        item = self.get_editable(pk)
        form = WishForm(request.POST, instance=item)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "item": item}, status=400)
        services.update_wish(item, request.user, **form.wish_data())
        messages.success(request, _("Cambios guardados."))
        return redirect("shopping:wish_detail", pk=item.pk)


class WishDetailView(WishMixin, TemplateView):
    template_name = "shopping/wish_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_wish(self.kwargs["pk"], stats=True)
        item.my_vote = self.my_votes([item]).get(item.pk)
        context.update(
            item=item,
            can_edit=item.can_edit(self.request.user),
            can_delete=item.can_delete(self.request.user, self.request.membership),
            statuses=WishItem.Status.choices,
            comments=item.comments.select_related("author"),
            comment_form=CommentForm(),
            colors=_member_colors(self.request.household),
        )
        if item.is_shared:
            context["voters"] = item.votes.select_related("user").order_by("-value", "created_at")
        return context


def _member_colors(household) -> dict:
    return dict(Membership.objects.filter(household=household).values_list("user_id", "color"))


class WishStatusView(WishMixin, View):
    def post(self, request, pk):
        item = self.get_wish(pk)
        try:
            services.change_status(item, request.user, request.POST.get("status", ""))
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        return redirect("shopping:wish_detail", pk=item.pk)


class WishShareView(WishMixin, View):
    def post(self, request, pk):
        services.make_shared(self.get_wish(pk), request.user)
        messages.success(request, _("Ahora es una propuesta común: el resto del hogar ya la ve."))
        return redirect("shopping:wish_detail", pk=pk)


class WishVoteView(WishMixin, View):
    def post(self, request, pk):
        item = self.get_wish(pk)
        try:
            value = int(request.POST.get("value", "0"))
        except ValueError:
            value = 0
        try:
            services.vote(item, request.user, value)
        except ValidationError:
            return HttpResponse(status=400)
        if not request.htmx:
            return redirect("shopping:wish_detail", pk=pk)
        item = self.get_wish(pk, stats=True)
        item.my_vote = self.my_votes([item]).get(item.pk)
        context = {"item": item, "detail": request.POST.get("detail") == "1"}
        if context["detail"]:
            context["voters"] = item.votes.select_related("user").order_by("-value", "created_at")
            context["colors"] = _member_colors(request.household)
        return render(request, "shopping/partials/votes.html", context)


class WishCommentView(WishMixin, View):
    def post(self, request, pk):
        item = self.get_wish(pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                services.add_comment(item, request.user, form.cleaned_data["body"])
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        return redirect(reverse("shopping:wish_detail", args=[pk]) + "#comentarios")


class WishDeleteView(WishMixin, View):
    """Borrado definitivo, llamado al expirar el aviso de "Deshacer" (ADR-010)."""

    def post(self, request, pk):
        services.delete_wish(self.get_wish(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        messages.success(request, _("Deseo borrado."))
        return redirect("shopping:wishes")


class CommentDeleteView(WishMixin, View):
    def post(self, request, pk):
        visible = services.wishes_for(request.user, request.household)
        comment = get_object_or_404(WishComment, pk=pk, item__in=visible)
        services.delete_comment(comment, request.user)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect(reverse("shopping:wish_detail", args=[comment.item_id]) + "#comentarios")
