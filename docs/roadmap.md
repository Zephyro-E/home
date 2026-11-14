# Roadmap y estado

Leyenda: ⬜ pendiente · 🟨 en curso · ✅ terminado y verificado

Cada fase sigue estos pasos: objetivo → requisitos → diseño de datos → backend → frontend → pruebas → validación funcional → documentación → commit/etiqueta en Git.
Una fase no se da por terminada sin pruebas pasando y validación funcional real.

| Fase | Contenido | Tamaño | Estado |
|---|---|---|---|
| **0. Cimientos** | Proyecto Django con uv, estructura, ajustes, Tailwind/HTMX/Alpine, ruff, pytest, CI en GitHub Actions, plantilla base con tema claro/oscuro, script de arranque | S | ✅ 2026-11-14 |
| **1. Identidad y hogar** | Usuario propio (login por email), Argon2, sesiones, asistente inicial, hogar, invitaciones, roles, middleware de hogar activo, `visible_to`, pruebas de autorización, perfil (idioma, tema, avatar), i18n es/en, dashboard vacío, manifest PWA, copia de seguridad + restauración | M | ⬜ |
| **2. Compras** | Lista de la compra cotidiana; deseos personales y comunes con estados, votos y comentarios; pasar de personal a común; "Deshacer" al borrar; widgets en dashboard | M | ⬜ |
| **3. Tareas** | Tablero Pendiente / En curso / Terminada con arrastrar y soltar, responsable, fecha límite, prioridad, etiquetas, subtareas, comentarios; widget | M | ⬜ |
| **— MVP —** | Uso real en casa durante ~2 semanas, copias automáticas, ajustes según la experiencia | | ⬜ |
| **4. Calendario** | Eventos y tipos, participantes, vistas mes / semana / agenda, recurrencias (RRULE), tareas proyectadas, tareas recurrentes | L | ⬜ |
| **5. Películas/series y Sitios** | CRUD con patrón común, valoraciones por persona, progreso de series, selección aleatoria de sitio pendiente | M | ⬜ |
| **6. Finanzas I** | Cuentas, categorías, ingresos/gastos, transferencias internas, resumen mensual | L | ⬜ |
| **7. Finanzas II** | Gastos compartidos (50/50 configurable + excepciones), saldos y liquidaciones, presupuestos, ahorro, gráficos | L | ⬜ |
| **8. Recetas** | Recetario, raciones, ingredientes → lista de la compra, imágenes | M | ⬜ |
| **9. Transversales** | Buscador global, notificaciones internas, exportación CSV/JSON, recuperación de contraseña | M | ⬜ |
| **10. Servidor** | Dockerfile + Docker Compose, HTTPS, posible paso a PostgreSQL, migración de datos desde el PC | M | ⬜ |
| **Futuro** | Planificador de comidas, mapa de sitios, TMDB, votación de películas, mantenimiento, inventario, documentos, estadísticas | — | ⬜ |

## Notas de la Fase 0

- Verificado: 14 pruebas automáticas, lint, página de inicio en escritorio y móvil, modo claro/oscuro, español/inglés según el navegador, servidor Waitress sin modo desarrollo (estáticos y página 404 genérica).
- Ya existe el usuario propio (login por email, Argon2): era obligatorio antes de la primera migración.
- Pendiente para la Fase 1: compilar traducciones en Windows sin instalar GNU gettext (opción prevista: Babel, en Python puro).

## Requisitos transversales: cuándo llega cada uno

| Requisito | Fase |
|---|---|
| Autenticación segura, autorización por usuario y hogar, personal/compartido | 1 |
| Diseño responsive, modo claro/oscuro, validación de formularios | 0–1 (y cada fase) |
| Zonas horarias consistentes | 1 (ajustes) · 4 (calendario) |
| Migraciones de base de datos | 0 (Django) |
| Registro de errores | 0 (logging a archivo) |
| Copias de seguridad y restauración | 1 |
| Pruebas automatizadas | 0 en adelante |
| PWA instalable | 1 (manifest) · HTTPS en fase 1 o 10 |
| Gestión de archivos e imágenes | 2 (URL) · 8 (subida) |
| Notificaciones internas, buscador global, exportación | 9 |
