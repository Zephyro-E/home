"""Middleware del núcleo.

- SetupRequiredMiddleware: mientras no exista ninguna cuenta, todo lleva al asistente inicial.
- CurrentHouseholdMiddleware (ADR-011): hogar activo en sesión, validado en cada petición;
  activa además el idioma del usuario y la zona horaria del hogar.
"""

import zoneinfo

from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone, translation

SESSION_KEY = "household_id"


class SetupRequiredMiddleware:
    _setup_done = False  # se cachea en memoria una vez que existe alguna cuenta

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not SetupRequiredMiddleware._setup_done:
            if get_user_model().objects.exists():
                SetupRequiredMiddleware._setup_done = True
            else:
                setup_url = reverse("core:setup")
                allowed = (setup_url, "/static/", "/i18n/", "/manifest.webmanifest")
                if not request.path.startswith(allowed):
                    return redirect(setup_url)
        return self.get_response(request)


class CurrentHouseholdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        request.household = None
        request.memberships = []

        user = request.user
        if user.is_authenticated:
            memberships = list(user.memberships.select_related("household"))
            request.memberships = memberships
            wanted = request.session.get(SESSION_KEY)
            current = next((m for m in memberships if str(m.household_id) == wanted), None)
            if current is None and memberships:
                current = memberships[0]
            if current is not None:
                request.membership = current
                request.household = current.household
                if wanted != str(current.household_id):
                    request.session[SESSION_KEY] = str(current.household_id)
            elif wanted:
                request.session.pop(SESSION_KEY, None)

            if user.language:
                translation.activate(user.language)
                request.LANGUAGE_CODE = user.language

        if request.household is not None:
            try:
                timezone.activate(zoneinfo.ZoneInfo(request.household.timezone))
            except zoneinfo.ZoneInfoNotFoundError:
                timezone.deactivate()
        else:
            timezone.deactivate()

        return self.get_response(request)
