from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Dashboard. En la Fase 0 es público y estático; en la Fase 1 exigirá iniciar sesión."""

    template_name = "core/home.html"
