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
        "unread_notifications": _unread(request),
    }


def _unread(request) -> int:
    from apps.notifications.services import unread_count

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return 0
    return unread_count(user, getattr(request, "household", None))
