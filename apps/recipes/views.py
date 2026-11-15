"""Vistas del recetario. Los datos parten de visible_to (services.recipes_for)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.core import images, social
from apps.core.mixins import HouseholdRequiredMixin
from apps.core.models import Membership

from . import services
from .forms import CommentForm, RecipeForm
from .models import Recipe, RecipeComment


def _colors(household) -> dict:
    return dict(Membership.objects.filter(household=household).values_list("user_id", "color"))


def _servings(text, default: int) -> int:
    try:
        value = int(text)
    except (TypeError, ValueError):
        return default
    return min(max(value, 1), services.MAX_SERVINGS)


class RecipeMixin(HouseholdRequiredMixin):
    def get_recipe(self, pk, editable=False):
        recipe = get_object_or_404(
            services.recipes_for(self.request.user, self.request.household), pk=pk
        )
        if editable and not recipe.can_edit(self.request.user):
            raise Http404
        return recipe


class RecipeListView(RecipeMixin, TemplateView):
    template_name = "recipes/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, household = self.request.user, self.request.household
        get = self.request.GET
        query = get.get("q", "").strip()[:100]
        course = get.get("tipo") if get.get("tipo") in Recipe.Course.values else ""
        tag = get.get("etiqueta", "").strip()[:40]
        context.update(
            items=services.listing(user, household, query, course, tag),
            query=query,
            course=course,
            tag=tag,
            courses=Recipe.Course.choices,
            tags=services.all_tags(user, household),
        )
        return context


class RecipeCreateView(RecipeMixin, View):
    template_name = "recipes/form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": RecipeForm()})

    def post(self, request):
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                recipe = services.create_recipe(
                    request.household, request.user, **form.recipe_data()
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Receta guardada."))
                return redirect("recipes:detail", pk=recipe.pk)
        return render(request, self.template_name, {"form": form}, status=400)


class RecipeEditView(RecipeMixin, View):
    template_name = "recipes/form.html"

    def get(self, request, pk):
        recipe = self.get_recipe(pk, editable=True)
        form = RecipeForm(
            instance=recipe, initial={"ingredients_text": services.ingredients_text(recipe)}
        )
        return render(request, self.template_name, {"form": form, "recipe": recipe})

    def post(self, request, pk):
        recipe = self.get_recipe(pk, editable=True)
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            try:
                services.update_recipe(recipe, request.user, **form.recipe_data())
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, _("Cambios guardados."))
                return redirect("recipes:detail", pk=pk)
        recipe.refresh_from_db()
        return render(request, self.template_name, {"form": form, "recipe": recipe}, status=400)


class RecipeDetailView(RecipeMixin, TemplateView):
    template_name = "recipes/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.get_recipe(self.kwargs["pk"])
        user = self.request.user
        servings = _servings(self.request.GET.get("raciones"), recipe.servings)
        context.update(social.rating_context(recipe, user))
        context.update(
            recipe=recipe,
            servings=servings,
            ingredients=services.scaled_ingredients(recipe, servings),
            can_edit=recipe.can_edit(user),
            can_delete=recipe.can_delete(user, self.request.membership),
            comments=recipe.comments.select_related("author"),
            colors=_colors(self.request.household),
            rate_url=reverse("recipes:rate", args=[recipe.pk]),
            target_id=f"rating-{recipe.pk}",
        )
        return context


class RecipeImageView(RecipeMixin, View):
    """Entrega la foto solo a quien puede ver la receta."""

    def get(self, request, pk):
        return images.serve(self.get_recipe(pk).image)


class AddToGroceryView(RecipeMixin, View):
    def post(self, request, pk):
        recipe = self.get_recipe(pk)
        servings = _servings(request.POST.get("servings"), recipe.servings)
        ids = [int(v) for v in request.POST.getlist("ingredient") if v.isdigit()]
        added = services.add_to_grocery(recipe, request.user, request.household, servings, ids)
        if added:
            messages.success(
                request, _("Añadidos %(n)s ingredientes a la lista de la compra.") % {"n": added}
            )
        else:
            messages.error(request, _("Elige al menos un ingrediente."))
        return redirect(reverse("recipes:detail", args=[pk]) + f"?raciones={servings}")


class ShareView(RecipeMixin, View):
    def post(self, request, pk):
        services.make_shared(self.get_recipe(pk), request.user)
        messages.success(request, _("Ahora la ve todo el hogar."))
        return redirect("recipes:detail", pk=pk)


class DeleteView(RecipeMixin, View):
    def post(self, request, pk):
        services.delete_recipe(self.get_recipe(pk), request.user, request.membership)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        messages.success(request, _("Receta borrada."))
        return redirect("recipes:list")


class RateView(RecipeMixin, View):
    def post(self, request, pk):
        recipe = self.get_recipe(pk)
        stars = request.POST.get("stars", "")
        try:
            services.rate(recipe, request.user, int(stars) if stars.isdigit() else 0)
        except ValidationError:
            return HttpResponse(status=400)
        if not request.htmx:
            return redirect("recipes:detail", pk=pk)
        context = social.rating_context(recipe, request.user)
        context.update(
            rate_url=reverse("recipes:rate", args=[pk]),
            target_id=f"rating-{pk}",
            colors=_colors(request.household),
        )
        return render(request, "partials/rating.html", context)


class CommentAddView(RecipeMixin, View):
    def post(self, request, pk):
        recipe = self.get_recipe(pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                services.add_comment(recipe, request.user, form.cleaned_data["body"])
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        return redirect(reverse("recipes:detail", args=[pk]) + "#comentarios")


class CommentDeleteView(RecipeMixin, View):
    def post(self, request, pk):
        visible = services.recipes_for(request.user, request.household)
        comment = get_object_or_404(RecipeComment, pk=pk, recipe__in=visible)
        social.delete_comment(comment, request.user)
        if request.headers.get("X-Undo-Commit"):
            return HttpResponse(status=204)
        return redirect(reverse("recipes:detail", args=[comment.recipe_id]) + "#comentarios")
