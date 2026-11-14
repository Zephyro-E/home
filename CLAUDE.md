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

- El vigilante de Tailwind (`tailwind runserver` / `watch`) se cierra si no hay consola (procesos en segundo plano): en ese caso, ejecutar `tailwind build` tras cambiar plantillas.
- El servidor de vista previa puede iniciarse con `.claude/launch.json` (configuración `hogar`).
- Verificación visual: escritorio y móvil (375 px), modo claro y oscuro, sin errores en consola.

## Mapa del código

- `config/settings.py`: toda la configuración, leída de variables `HOGAR_*` (ver `.env.example`).
- `apps/core/`: usuario propio (`models.User`, login por email), registro de módulos (`modules.py`), navegación (`context_processors.py`), etiqueta `{% icon %}` (`templatetags/ui.py`).
- `templates/base.html`: estructura de la app (barra lateral, cabecera móvil, barra inferior); `templates/partials/`: componentes.
- `assets/css/source.css`: colores semánticos (`bg-surface`, `text-muted`, `bg-accent`…) para claro/oscuro. Usarlos en lugar de colores fijos.
- `static/icons/`: iconos Lucide 0.460.0. Para añadir uno: descargar `https://cdn.jsdelivr.net/npm/lucide-static@0.460.0/icons/<nombre>.svg`.
