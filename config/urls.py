from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.i18n import set_language

urlpatterns = [
    path("admin/", admin.site.urls),
    # Cambio de idioma (también disponible sin sesión, p. ej. en la página de entrada).
    path("i18n/setlang/", login_not_required(set_language), name="set_language"),
    path("compras/", include("apps.shopping.urls")),
    path("tareas/", include("apps.tasks.urls")),
    path("calendario/", include("apps.events.urls")),
    path("peliculas/", include("apps.media.urls")),
    path("sitios/", include("apps.places.urls")),
    path("finanzas/", include("apps.finance.urls")),
    path("recetas/", include("apps.recipes.urls")),
    path("", include("apps.core.urls")),
]
