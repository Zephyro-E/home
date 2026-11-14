# Diseño UX/UI

## Principios

1. **Capturar en menos de 5 segundos**: botón "+" global para añadir un producto, tarea o deseo.
2. **Pocos campos visibles**; el resto tras "Más opciones".
3. **Sin pantallas vacías ni recargadas**: los widgets del dashboard solo aparecen si tienen algo que mostrar.
4. **Deshacer mejor que confirmar** (ver ADR-010).
5. **Pensado primero para móvil**, aprovechando el ancho en escritorio.

## Navegación

- **Móvil**: barra inferior con *Inicio · Compras · Tareas · Calendario · Más* + botón flotante "+".
- **Escritorio**: barra lateral plegable con todos los módulos; cabecera con avatar (y, más adelante, buscador y notificaciones).
- Selector de hogar solo si se pertenece a más de uno.
- Formularios: hoja inferior en móvil, diálogo/panel lateral en escritorio.

## Dashboard (móvil)

```
┌───────────────────────────┐
│ Hola, Eduardo · sáb 14 nov │
├───────────────────────────┤
│ HOY                        │
│ ● 18:00 Dentista           │
│ ☐ Sacar basura · vence hoy │
├───────────────────────────┤
│ 🛒 Lista compra   7 items →│
│ 🗳 2 propuestas por votar →│
├───────────────────────────┤
│ [Compras] [Tareas] [Calend]│
│ [Recetas] [Sitios] [Pelis] │
├───────────────────────────┤
│ 🏠  🛒  ✓  📅  ⋯       (+) │
└───────────────────────────┘
```

## Línea visual

- Base neutra cálida (gama *stone* de Tailwind), un único color de acento para acciones principales y un color suave por módulo (solo iconos y cabeceras).
- Un color por miembro del hogar (avatares, responsables, eventos).
- Tipografía del sistema / Inter; esquinas 12–16 px; sombras sutiles; espaciado generoso; iconos Lucide.
- Modo claro y oscuro mediante variables de color desde la Fase 0; por defecto sigue al sistema.

## Accesibilidad

Contraste WCAG AA, objetivos táctiles ≥ 44 px, foco visible, etiquetas en todos los controles, respeto a `prefers-reduced-motion`, navegación por teclado.

## Componentes reutilizables (plantillas parciales)

`app_shell`, `module_header`, `item_card` / `list_row`, `visibility_toggle` (candado personal/compartido), `status_badge`, `priority_indicator`, `vote_buttons`, `comment_thread`, `avatar` / `avatar_stack`, `rating_stars`, `form_sheet`, `empty_state`, `toast` (con Deshacer), `skeleton`.
