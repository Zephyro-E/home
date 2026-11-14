# Requisitos y decisiones funcionales

Resumen del encargo inicial (2026-11-13) y de las decisiones tomadas después. El detalle técnico está en [decisiones.md](decisiones.md).

## Objetivo

Centro de gestión doméstica compartido entre los miembros de un hogar: sencillo para personas sin conocimientos informáticos, moderno, modular, seguro, usable en móvil y PC, con datos reales persistentes. Desarrollo incremental por fases.

## Contexto de uso

- Un hogar, dos personas al inicio; el modelo admite varios hogares y más miembros.
- Alojada en el PC de casa y usada solo dentro de casa; más adelante se trasladará a un servidor particular.
- El propietario no programa: desarrollo asistido por IA. La documentación debe permitir retomar el proyecto tras semanas.

## Decisiones funcionales cerradas (2026-11-14)

| Tema | Decisión |
|---|---|
| Registro | Solo por invitación |
| Edición de elementos compartidos | Cualquier miembro |
| Cambiar estado de compras (aprobar…) | Cualquier miembro; los votos no cambian el estado automáticamente |
| Votos | Uno por persona y propuesta; modificable y retirable; siempre visibles para el hogar |
| Lista de la compra cotidiana | Incluida en el MVP |
| Moneda | Euro |
| Reparto de gastos | 50/50 por defecto, configurable por hogar, con excepciones por gasto |
| Idiomas | Español (principal) e inglés |
| Borrado | Definitivo, con "Deshacer" durante unos segundos; sin papelera |
| Privacidad | Lo privado solo lo ve su dueño, también frente a quien administra |

## Módulos

| Módulo | Fase | Notas |
|---|---|---|
| Compras y deseos (+ lista cotidiana) | 2 | MVP |
| Tareas | 3 | MVP |
| Calendario | 4 | Integra tareas con fecha límite sin duplicarlas |
| Películas y series | 5 | TMDB en el futuro |
| Sitios | 5 | Mapa en el futuro |
| Finanzas | 6–7 | Sin integraciones bancarias |
| Recetas | 8 | Planificador semanal en el futuro |
| Mantenimiento, inventario, documentos, estadísticas | Futuro | No se implementan en las primeras fases |

## Fuera de alcance por ahora

Funcionamiento sin conexión con sincronización, notificaciones push, integraciones bancarias, apps nativas, API pública.
