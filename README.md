# Hogar

Aplicación web para gestionar la vida cotidiana de un hogar: lista de la compra y deseos, tareas, calendario, finanzas, recetas, sitios que visitar y películas/series. Pensada para usarse desde el móvil y el ordenador, compartida entre los miembros del hogar y con información personal privada.

> **Estado:** fase de diseño completada; desarrollo pendiente de empezar (Fase 0). Ver [docs/roadmap.md](docs/roadmap.md).

## Tecnología

Python 3.13 · Django 5.2 LTS · HTMX · Alpine.js · Tailwind CSS · SQLite. Detalle en [docs/arquitectura.md](docs/arquitectura.md).

## Documentación

| Documento | Contenido |
|---|---|
| [docs/requisitos.md](docs/requisitos.md) | Objetivo, módulos y decisiones funcionales |
| [docs/arquitectura.md](docs/arquitectura.md) | Stack, estructura, seguridad, copias de seguridad |
| [docs/decisiones.md](docs/decisiones.md) | Registro de decisiones técnicas (ADR) |
| [docs/modelo-datos.md](docs/modelo-datos.md) | Entidades, relaciones y permisos |
| [docs/diseno-ux.md](docs/diseno-ux.md) | Navegación, línea visual y componentes |
| [docs/roadmap.md](docs/roadmap.md) | Fases y estado actual |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios |

## Puesta en marcha

Se documentará al completar la Fase 0.

## Privacidad

Este repositorio es público y contiene solo código y documentación. Los datos del hogar (base de datos, imágenes, copias de seguridad, `.env`) viven en la carpeta `data/` y nunca se suben a Git.
