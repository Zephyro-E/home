from django.urls import reverse

from .modules import MODULES


def navigation(request):
    """Pone la navegación a disposición de todas las plantillas."""
    match = getattr(request, "resolver_match", None)
    if match and match.view_name == "core:home":
        active = "home"
    else:
        active = match.namespace if match else ""
    return {
        "modules": MODULES,
        "bottom_nav_modules": [m for m in MODULES if m.in_bottom_nav],
        "home_url": reverse("core:home"),
        "nav_active": active,
    }
