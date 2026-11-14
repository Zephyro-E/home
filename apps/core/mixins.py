"""Mixins de vista para la autorización (ADR-005).

Todas las vistas exigen sesión iniciada por defecto (LoginRequiredMiddleware).
Las vistas de módulos deben heredar de HouseholdRequiredMixin y obtener sus datos con
`Model.objects.visible_to(request.user, request.household)`.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class HouseholdRequiredMixin:
    """Exige un hogar activo. Si la persona no pertenece a ninguno, la lleva a crear uno."""

    def dispatch(self, request, *args, **kwargs):
        if request.household is None:
            return redirect("core:no_household")
        return super().dispatch(request, *args, **kwargs)


class HouseholdAdminRequiredMixin(HouseholdRequiredMixin):
    """Exige además el rol de administración en el hogar activo."""

    def dispatch(self, request, *args, **kwargs):
        if request.household is not None and not request.membership.is_admin:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
