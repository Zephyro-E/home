# CLAUDE.md

Guía para asistentes de IA que trabajen en este repositorio.

## Contexto del propietario

- El propietario **no programa**: todo el desarrollo se hace con asistentes de IA. Explica las decisiones en lenguaje claro, en **español**, sin dar por supuesto conocimiento técnico.
- Antes de cambios arquitectónicos importantes, explica implicaciones y pide confirmación.
- **No inventes resultados de pruebas** ni declares terminada una funcionalidad sin haberla verificado (pruebas + comprobación en navegador).

## Dónde está todo

- Requisitos y decisiones funcionales: `docs/requisitos.md`
- Arquitectura y stack: `docs/arquitectura.md`
- Decisiones técnicas (ADR): `docs/decisiones.md` — añade un ADR nuevo para cualquier decisión relevante
- Modelo de datos: `docs/modelo-datos.md`
- Diseño UX/UI: `docs/diseno-ux.md`
- Fases y estado: `docs/roadmap.md` — actualízalo al empezar y terminar cada fase

## Reglas del proyecto

- Stack: Django 5.2 LTS + HTMX + Alpine.js + Tailwind (binario independiente) + SQLite. Python gestionado con `uv`. No añadir Node.js ni frameworks de frontend sin un ADR.
- Monolito modular: una app Django por módulo dentro de `apps/`. Lógica de negocio en `services.py`, no en las vistas.
- **Permisos (ADR-005)**: todo modelo de dominio hereda de `HouseholdOwnedModel`; todo queryset parte de `visible_to(user, household)`; acceso no permitido → 404. Cada vista nueva lleva pruebas de autorización (otro miembro, otro hogar, anónimo).
- Importes en céntimos enteros (ADR-007). Fechas en UTC; fechas sin hora como `date` (ADR-008).
- Textos de interfaz en español envueltos para traducción (`{% translate %}`, `gettext`); traducción inglesa en `locale/en/` (ADR-009).
- Nunca subir a Git: `data/`, `.env`, bases de datos, imágenes de usuarios, copias. **El repositorio es público.**
- Trabajo por fases (ver roadmap). Cada fase: pruebas pasando, validación funcional, documentación actualizada, entrada en `CHANGELOG.md`, commit con mensaje claro (convención: `feat:`, `fix:`, `docs:`, `chore:`, `test:`).

## Comandos

uv se instala en `%USERPROFILE%\.local\bin`; si no está en el PATH de la shell, añadirlo (`export PATH="$HOME/.local/bin:$PATH"`).

```bash
uv run pytest                                    # pruebas (deben pasar antes de cada commit)
uv run ruff check . && uv run ruff format --check .   # lint y formato (la CI los exige)
uv run python manage.py makemigrations / migrate
uv run python manage.py tailwind build           # recompilar CSS tras tocar plantillas
HOGAR_DEBUG=1 uv run python manage.py tailwind runserver   # desarrollo (scripts/arrancar.bat)
```

```bash
uv run python manage.py translations update      # tras añadir textos: los vuelca a locale/en/LC_MESSAGES/django.po
uv run python manage.py translations compile     # tras traducir: genera el .mo (se versiona)
uv run python manage.py backup / restore <copia>
```

- Las pruebas usan `config/settings_test.py` (añade `apps/core/tests/testapp`, un modelo de ejemplo con el patrón de permisos, y contraseñas rápidas). Fixtures comunes en `apps/conftest.py`: `home` (Ana admin + Luis miembro), `other_home` (Eva), `make_user`, `login_as`.
- Una prueba falla si hay textos sin traducir: tras tocar textos, `translations update`, traducir en el `.po` y `translations compile`.
- `data/` contiene los datos reales del propietario: no borrarla ni hacer pruebas contra ella. Para probar en el navegador usar otra carpeta: `HOGAR_DATA_DIR=<carpeta temporal>` y otro puerto.
- El vigilante de Tailwind (`tailwind runserver` / `watch`) se cierra si no hay consola (procesos en segundo plano): en ese caso, ejecutar `tailwind build` tras cambiar plantillas.
- El servidor de vista previa puede iniciarse con `.claude/launch.json` (configuración `hogar`).
- Verificación visual: escritorio y móvil (375 px), modo claro y oscuro, sin errores en consola.

## Mapa del código

- `config/settings.py`: toda la configuración, leída de variables `HOGAR_*` (ver `.env.example`).
- `apps/core/models.py`: `User`, `Household`, `Membership` (rol, color, reparto), `Invitation` (solo hash del token), `HouseholdOwnedModel` + `visible_to()` (ADR-005).
- `apps/core/middleware.py`: asistente inicial obligatorio sin cuentas; hogar activo (`request.household`, `request.membership`), idioma del usuario y zona horaria del hogar.
- `apps/core/mixins.py`: `HouseholdRequiredMixin`, `HouseholdAdminRequiredMixin`. Todas las vistas exigen sesión (ADR-015); las públicas llevan `@login_not_required`.
- `apps/core/services.py`: lógica de hogares, miembros, invitaciones y bloqueo de intentos de login. `backup.py`: copias.
- `apps/core/`: registro de módulos (`modules.py`), navegación (`context_processors.py`), etiquetas `{% icon %}` y `{% member_color %}` (`templatetags/ui.py`).
- Plantillas: `base.html` (app con sesión), `base_auth.html` (entrada, asistente, invitación); componentes en `templates/partials/` (`form_fields`, `avatar`, `user_menu`, `messages`…).
- `assets/css/source.css`: colores semánticos (`bg-surface`, `text-muted`, `bg-accent`…) para claro/oscuro. Usarlos en lugar de colores fijos.
- `apps/core/money.py`: importes (texto ↔ céntimos, formato "12,50 €"); filtros `euros` y `get_item` en `ui.py`.
- `apps/finance/`: cuentas, categorías y movimientos; privacidad por cuenta (ADR-019): `Transaction.visibility` la calcula `services._prepare`, nunca el formulario. Saldos con `services.balances()`.
- Valorar y comentar: `apps/core/social.py` (`AbstractRating`, `AbstractComment`, `rate`, `with_rating`) + `partials/rating.html` y `partials/comments.html`. Ejemplos: `apps/media/`, `apps/places/`.
- `apps/events/`: calendario (URL `calendar:`), `items_between()` expande repeticiones y proyecta tareas (ADR-018). Repeticiones comunes en `apps/core/recurrence.py` y `RecurrenceFieldsMixin` (`core/forms.py`) + `partials/recurrence_fields.html`.
- `apps/tasks/`: tablero de tareas (SortableJS, ADR-017; componente Alpine `taskColumn` en `app.js`). Ojo: en consultas con recuentos (`annotate(Count…)`) Django no aplica `Meta.ordering`: poner `order_by` explícito.
- `apps/shopping/`: lista de la compra y deseos (modelo de referencia para los módulos siguientes: services, vistas con HTMX, pruebas de autorización).
- Borrar con "Deshacer" (ADR-016): `x-data="deletable"` + `data-delete-url` / `data-ids` / `data-undo-message`; la vista responde 204 si llega `X-Undo-Commit`.
- `static/icons/`: iconos Lucide 0.460.0. Para añadir uno: descargar `https://cdn.jsdelivr.net/npm/lucide-static@0.460.0/icons/<nombre>.svg`.
