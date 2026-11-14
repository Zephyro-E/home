from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone, translation
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, TemplateView, UpdateView

from . import services
from .forms import (
    HouseholdForm,
    LoginForm,
    NewAccountForm,
    ProfileForm,
    SetupForm,
    StyledPasswordChangeForm,
)
from .middleware import SESSION_KEY
from .mixins import HouseholdAdminRequiredMixin, HouseholdRequiredMixin
from .models import Invitation, Membership, User

UserModel = get_user_model()


def _error_text(error: ValidationError) -> str:
    return " ".join(error.messages)


# --- Acceso ------------------------------------------------------------------------------


class LoginView(auth_views.LoginView):
    template_name = "core/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@method_decorator(login_not_required, name="dispatch")
class SetupView(FormView):
    """Asistente inicial: solo disponible mientras no exista ninguna cuenta."""

    template_name = "core/setup.html"
    form_class = SetupForm

    def dispatch(self, request, *args, **kwargs):
        if UserModel.objects.exists():
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        user, _household = services.setup_first_user(
            household_name=data["household_name"],
            name=data["name"],
            email=data["email"],
            password=data["password1"],
        )
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, _("¡Listo! Tu hogar está creado."))
        return redirect("core:home")


@method_decorator(login_not_required, name="dispatch")
class AcceptInvitationView(View):
    template_name = "core/invitation.html"

    def get_invitation(self, token):
        return Invitation.find_valid(token)

    def render_page(self, request, invitation, form=None, status=200):
        context = {"invitation": invitation, "form": form, "token": self.kwargs["token"]}
        if invitation is None:
            context["error"] = services.invitation_error(None)
            status = 410
        elif request.user.is_authenticated:
            context["already_member"] = Membership.objects.filter(
                household=invitation.household, user=request.user
            ).exists()
        return render(request, self.template_name, context, status=status)

    def get(self, request, token):
        invitation = self.get_invitation(token)
        form = None if request.user.is_authenticated else NewAccountForm()
        return self.render_page(request, invitation, form)

    def post(self, request, token):
        invitation = self.get_invitation(token)
        if invitation is None:
            return self.render_page(request, None)

        if request.user.is_authenticated:
            try:
                membership = services.accept_invitation(invitation, request.user)
            except ValidationError as error:
                messages.error(request, _error_text(error))
                return self.render_page(request, invitation)
            request.session[SESSION_KEY] = str(membership.household_id)
            messages.success(
                request, _("Te has unido a %(name)s.") % {"name": invitation.household}
            )
            return redirect("core:home")

        form = NewAccountForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, invitation, form, status=400)
        data = form.cleaned_data
        try:
            user = services.register_with_invitation(
                invitation, name=data["name"], email=data["email"], password=data["password1"]
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.render_page(request, invitation, form, status=400)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session[SESSION_KEY] = str(invitation.household_id)
        messages.success(
            request, _("¡Te damos la bienvenida a %(name)s!") % {"name": invitation.household}
        )
        return redirect("core:home")


# --- Inicio ------------------------------------------------------------------------------


class HomeView(HouseholdRequiredMixin, TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["member_count"] = self.request.household.memberships.count()
        context["today"] = timezone.localdate()
        return context


class NoHouseholdView(FormView):
    """Para quien no pertenece a ningún hogar: puede crear uno nuevo."""

    template_name = "core/no_household.html"
    form_class = HouseholdForm

    def dispatch(self, request, *args, **kwargs):
        if request.household is not None and request.method == "GET":
            return redirect("core:home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        household = services.create_household(form.cleaned_data["name"], self.request.user)
        self.request.session[SESSION_KEY] = str(household.pk)
        messages.success(self.request, _("Hogar creado."))
        return redirect("core:home")


@require_POST
def switch_household(request, household_id):
    membership = get_object_or_404(Membership, household_id=household_id, user=request.user)
    request.session[SESSION_KEY] = str(membership.household_id)
    return redirect("core:home")


# --- Hogar: miembros e invitaciones ------------------------------------------------------


class HouseholdSettingsView(HouseholdRequiredMixin, TemplateView):
    template_name = "core/household.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = self.request.household
        context["memberships"] = household.memberships.select_related("user")
        context["is_admin"] = self.request.membership.is_admin
        context["roles"] = Membership.Role.choices
        if context["is_admin"]:
            context["form"] = kwargs.get("form") or HouseholdForm(instance=household)
            context["invitations"] = household.invitations.pending()
            context["new_invite_url"] = self.request.session.pop("new_invite_url", None)
        return context


class HouseholdRenameView(HouseholdAdminRequiredMixin, View):
    def post(self, request):
        form = HouseholdForm(request.POST, instance=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, _("Nombre del hogar actualizado."))
            return redirect("core:household")
        view = HouseholdSettingsView()
        view.setup(request)
        return view.render_to_response(view.get_context_data(form=form), status=400)


class InvitationCreateView(HouseholdAdminRequiredMixin, View):
    def post(self, request):
        role = request.POST.get("role", Membership.Role.MEMBER)
        if role not in Membership.Role.values:
            role = Membership.Role.MEMBER
        _invitation, token = Invitation.create_for(request.household, request.user, role=role)
        url = request.build_absolute_uri(reverse("core:invitation", args=[token]))
        request.session["new_invite_url"] = url
        return redirect(reverse("core:household") + "#invitaciones")


class InvitationRevokeView(HouseholdAdminRequiredMixin, View):
    def post(self, request, pk):
        invitation = get_object_or_404(request.household.invitations.pending(), pk=pk)
        invitation.delete()
        messages.success(request, _("Invitación anulada."))
        return redirect(reverse("core:household") + "#invitaciones")


class MemberRoleView(HouseholdAdminRequiredMixin, View):
    def post(self, request, pk):
        membership = get_object_or_404(request.household.memberships, pk=pk)
        try:
            services.change_role(membership, request.POST.get("role", ""))
            messages.success(request, _("Rol actualizado."))
        except ValidationError as error:
            messages.error(request, _error_text(error))
        return redirect("core:household")


class MemberRemoveView(HouseholdAdminRequiredMixin, View):
    def post(self, request, pk):
        membership = get_object_or_404(request.household.memberships, pk=pk)
        if membership.user_id == request.user.pk:
            raise Http404  # para salir uno mismo se usa "Salir del hogar"
        try:
            services.remove_member(membership)
            messages.success(
                request, _("%(name)s ya no forma parte del hogar.") % {"name": membership.user}
            )
        except ValidationError as error:
            messages.error(request, _error_text(error))
        return redirect("core:household")


class LeaveHouseholdView(HouseholdRequiredMixin, View):
    def post(self, request):
        try:
            services.remove_member(request.membership)
        except ValidationError as error:
            messages.error(request, _error_text(error))
            return redirect("core:household")
        request.session.pop(SESSION_KEY, None)
        messages.success(request, _("Has salido del hogar."))
        return redirect("core:home")


# --- Perfil ------------------------------------------------------------------------------


class ProfileView(UpdateView):
    template_name = "core/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("core:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        # El mensaje ya en el idioma recién elegido.
        translation.activate(form.instance.language)
        messages.success(self.request, _("Perfil guardado."))
        return response


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "core/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("core:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Contraseña cambiada."))
        return response


@require_POST
def save_theme(request):
    """Guarda el tema elegido con el botón de la cabecera (lo llama static/js/app.js)."""
    theme = request.POST.get("theme", "")
    if theme not in User.Theme.values:
        return HttpResponse(status=400)
    request.user.theme = theme
    request.user.save(update_fields=["theme"])
    return HttpResponse(status=204)
