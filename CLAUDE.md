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

Se completarán en la Fase 0.
