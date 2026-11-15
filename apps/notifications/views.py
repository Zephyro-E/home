from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import HouseholdRequiredMixin

from . import services


class NotificationListView(HouseholdRequiredMixin, TemplateView):
    template_name = "notifications/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, household = self.request.user, self.request.household
        services.purge_old(user, household)
        context["items"] = list(services.notifications_for(user, household)[:100])
        context["colors"] = dict(household.memberships.values_list("user_id", "color"))
        return context


class NotificationOpenView(HouseholdRequiredMixin, View):
    """Marca el aviso como leído y lleva a su elemento."""

    def get(self, request, pk):
        notification = get_object_or_404(
            services.notifications_for(request.user, request.household), pk=pk
        )
        services.mark_read(notification)
        url = notification.url
        if not url or not url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            url = "notifications:list"
        return redirect(url)


class MarkAllReadView(HouseholdRequiredMixin, View):
    def post(self, request):
        services.mark_all_read(request.user, request.household)
        return redirect("notifications:list")
