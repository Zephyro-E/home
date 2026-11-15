# Roadmap y estado

Leyenda: ⬜ pendiente · 🟨 en curso · ✅ terminado y verificado

Cada fase sigue estos pasos: objetivo → requisitos → diseño de datos → backend → frontend → pruebas → validación funcional → documentación → commit/etiqueta en Git.
Una fase no se da por terminada sin pruebas pasando y validación funcional real.

| Fase | Contenido | Tamaño | Estado |
|---|---|---|---|
| **0. Cimientos** | Proyecto Django con uv, estructura, ajustes, Tailwind/HTMX/Alpine, ruff, pytest, CI en GitHub Actions, plantilla base con tema claro/oscuro, script de arranque | S | ✅ 2026-11-14 |
| **1. Identidad y hogar** | Usuario propio (login por email), Argon2, sesiones, asistente inicial, hogar, invitaciones, roles, middleware de hogar activo, `visible_to`, pruebas de autorización, perfil (idioma, tema, avatar), i18n es/en, dashboard vacío, manifest PWA, copia de seguridad + restauración | M | ✅ 2026-11-14 |
| **2. Compras** | Lista de la compra cotidiana; deseos personales y comunes con estados, votos y comentarios; pasar de personal a común; "Deshacer" al borrar; widgets en dashboard | M | ✅ 2026-11-15 |
| **3. Tareas** | Tablero Pendiente / En curso / Terminada con arrastrar y soltar, responsable, fecha límite, prioridad, etiquetas, subtareas, comentarios; widget | M | ✅ 2026-11-15 |
| **— MVP —** | Uso real en casa durante ~2 semanas, copias automáticas, ajustes según la experiencia | | ⬜ |
| **4. Calendario** | Eventos y tipos, participantes, vistas mes / semana / agenda, recurrencias (RRULE), tareas proyectadas, tareas recurrentes | L | ✅ 2026-11-15 |
| **5. Películas/series y Sitios** | CRUD con patrón común, valoraciones por persona, progreso de series, selección aleatoria de sitio pendiente | M | ✅ 2026-11-15 |
| **6. Finanzas I** | Cuentas, categorías, ingresos/gastos, transferencias internas, resumen mensual | L | ✅ 2026-11-15 |
| **7. Finanzas II** | Gastos compartidos (50/50 configurable + excepciones), saldos y liquidaciones, presupuestos, ahorro, gráficos | L | ✅ 2026-11-15 |
| **8. Recetas** | Recetario, raciones, ingredientes → lista de la compra, imágenes | M | ✅ 2026-11-15 |
| **9. Transversales** | Buscador global, notificaciones internas, exportación CSV/JSON, recuperación de contraseña | M | ⬜ |
| **10. Servidor** | Dockerfile + Docker Compose, HTTPS, posible paso a PostgreSQL, migración de datos desde el PC | M | ⬜ |
| **Futuro** | Planificador de comidas, mapa de sitios, TMDB, votación de películas, mantenimiento, inventario, documentos, estadísticas | — | ⬜ |

## Notas de la Fase 0

- Verificado: 14 pruebas automáticas, lint, página de inicio en escritorio y móvil, modo claro/oscuro, español/inglés según el navegador, servidor Waitress sin modo desarrollo (estáticos y página 404 genérica).
- Ya existe el usuario propio (login por email, Argon2): era obligatorio antes de la primera migración.
- Pendiente para la Fase 1: compilar traducciones en Windows sin instalar GNU gettext (opción prevista: Babel, en Python puro).

## Notas de la Fase 1

- Verificado: 66 pruebas automáticas (permisos, acceso, invitaciones, miembros, perfil, copias, traducciones) y recorrido completo en el navegador: asistente inicial → crear invitación → alta de un segundo miembro con el enlace → enlace reutilizado rechazado → perfil en inglés y modo oscuro → menú en móvil. Copia y restauración probadas con datos reales.
- Cambios respecto al plan: el **avatar** es de iniciales con el color del miembro; la subida de fotos se hará con la gestión de archivos (Fase 8) (ADR-014). La **recuperación de contraseña** por email sigue en la Fase 9; mientras, se cambia desde el panel de administración o con `manage.py changepassword`.
- HTTPS para la PWA: resuelto con Tailscale (ADR-022, 2026-11-16).

## Notas de la Fase 2

- Verificado: 144 pruebas automáticas (reglas de compras, permisos de cada vista: otro miembro, otro hogar, anónimo) y recorrido en el navegador sobre una copia aparte: añadir productos sin recargar, marcar, borrar con "Deshacer" (deshecho y definitivo), "Quitar comprados", votar, cambiar estado, comentar, crear un deseo personal con precio, proponerlo al hogar y borrarlo; móvil y modo oscuro.
- Decisiones: la lista de la compra no duplica productos (si se vuelve a añadir uno comprado, vuelve a "Por comprar"); un deseo personal puede pasar a común pero no al revés (ya puede tener votos y comentarios); solo se vota y comenta en propuestas comunes; el borrado pendiente se confirma al salir de la página (ADR-016).
- Imágenes de deseos: solo mediante enlace (se cargan sin enviar la dirección de origen). La subida de fotos llega en la Fase 8.
- Pendiente para más adelante: la lista no se actualiza sola si otra persona la cambia a la vez (hay que recargar); botón "+" global para añadir desde cualquier pantalla.

## Notas de la Fase 3

- Verificado: 212 pruebas automáticas (reglas de tareas y autorización de cada vista: otro miembro, otro hogar, anónimo) y recorrido en el navegador sobre una copia aparte: arrastrar entre columnas y reordenar (guardado tras recargar), alta rápida, botones Empezar / Terminar / Reabrir, subtareas, aviso "Para hoy" en el inicio, móvil y modo oscuro.
- Diseño: en el móvil y en tablets se ve una columna cada vez, con pestañas; para cambiar de columna basta el botón de la tarjeta (arrastrar también funciona manteniendo pulsado). La columna "Terminada" muestra las 20 más recientes.
- Decisiones: una tarea personal solo puede asignarse a su dueño (nadie más la vería); el responsable debe ser miembro del hogar; las etiquetas son comunes y cualquier miembro puede crearlas o borrarlas (borrar una etiqueta no borra tareas); se pueden comentar también las tareas personales (como notas propias).
- Fallos encontrados y corregidos en la verificación: SortableJS se cargaba después de Alpine y el arrastre no se activaba; las columnas perdían el orden al contar subtareas (Django ignora el orden por defecto en consultas agrupadas).
- Pendiente para la Fase 4: tareas recurrentes (RRULE) y su proyección en el calendario.

## Notas de la Fase 4

- Verificado: 270 pruebas automáticas (reglas de repetición, expansión con cambio de horario, eventos de varios días, proyección de tareas, tareas recurrentes y autorización de cada vista) y recorrido en el navegador sobre una copia aparte: mes, semana y agenda; cumpleaños con "todo el día" y "cada año" automáticos; tarea semanal que al terminarse crea la siguiente; aviso "Para hoy" con eventos y tareas; móvil y modo oscuro.
- Diseño: vistas generadas en el servidor, sin FullCalendar (ADR-018). En el móvil el mes muestra puntos de color y la lista del día elegido debajo.
- Decisiones: editar o borrar un evento repetido afecta a toda la serie (no se editan repeticiones sueltas); una tarea recurrente necesita fecha límite y, al terminarla, se crea la siguiente con la primera fecha posterior a hoy; en un evento personal solo participa su dueño. Repetición "cada mes" el día 31 se salta los meses sin día 31.
- Pendiente para más adelante: excepciones en una serie (cambiar o quitar un único día), recordatorios/notificaciones (Fase 9).

## Notas de la Fase 5

- Verificado: 341 pruebas automáticas (reglas y autorización de cada vista en ambos módulos) y recorrido en el navegador sobre una copia aparte: listados con filtros y búsqueda, valorar con estrellas, progreso de series ("visto un episodio más"), "¿Qué vemos?" y "¿Dónde vamos?" al azar sin repetir el anterior, marcar un sitio como visitado; móvil y modo oscuro.
- Piezas comunes nuevas: valoraciones y comentarios (`apps/core/social.py`, `partials/rating.html`, `partials/comments.html`), reutilizables en recetas y siguientes módulos.
- Decisiones: el progreso de una serie es de cada persona; apuntar progreso pasa una serie "por ver" a "viendo"; "¿Qué vemos?" también se añadió para películas y series (el plan solo lo pedía para sitios); "Ver en el mapa" abre una búsqueda en OpenStreetMap (no se usa ninguna API ni se envía nada hasta que se pulsa).
- Mejora de navegación: en el móvil, "Más" muestra arriba los módulos que no caben en la barra inferior.
- Pendiente (futuro): mapa con los sitios, datos automáticos de películas (TMDB), votación de qué ver.

## Notas de la Fase 6

- Verificado: 384 pruebas automáticas (saldos, privacidad de cuentas y movimientos, resumen mensual sin transferencias, validaciones y autorización de cada vista) y recorrido en el navegador sobre una copia aparte, entrando como miembro sin administración: resumen, saldos, aportación desde una cuenta personal ajena mostrada como "Cuenta personal de Ana", formulario con "Guardar y añadir otro", móvil y modo oscuro.
- Privacidad (ADR-019): las cuentas son comunes o personales; un movimiento que toca una cuenta común es común; para editarlo hay que poder usar todas sus cuentas. La privacidad de una cuenta no se cambia después.
- Categorías por defecto (supermercado, casa y facturas, restaurantes…) que se crean solas la primera vez; comunes al hogar. Una cuenta con movimientos no se borra: se archiva.
- Fallo encontrado y corregido en la verificación: el resumen se desbordaba 13 px en el móvil.
- Pendiente para la Fase 7: gastos compartidos y repartos, saldos entre miembros, presupuestos, ahorro y gráficos.

## Notas de la Fase 7

- Verificado: 415 pruebas automáticas (reparto al céntimo, reparto por defecto normalizado, saldos, pagos mínimos para saldar, presupuestos, metas, gráfico y autorización de cada vista) y recorrido en el navegador sobre una copia aparte como miembro sin administración: gráfico de 12 meses, presupuestos (en verde, ámbar y rojo), "Luis debe 30 € a Ana" → "Registrar pago" con el formulario relleno → "Estáis en paz", formulario de gasto compartido con total en vivo, metas de ahorro, móvil y modo oscuro.
- Reglas (ADR-019 ampliado): solo se reparte lo pagado con una cuenta personal (lo de la cuenta común ya es de todos); un gasto compartido lo ve todo el hogar; el reparto por defecto lo decide la administración y en cada gasto se puede cambiar; el céntimo sobrante va a quien tenga mayor resto.
- Presupuestos mensuales por categoría, comunes al hogar: cuentan los gastos comunes y los compartidos. Metas de ahorro con cuenta vinculada (progreso = saldo) o con aportaciones a mano.
- Gráficos generados en el servidor, sin Chart.js (ADR-020).
- Fallos encontrados y corregidos en la verificación: el enlace "Registrar pago" no rellenaba el formulario (los identificadores llevan guiones); en el móvil, la pestaña activa de finanzas quedaba fuera de la vista.
- Nota de verificación: con el panel del navegador oculto, la página no dibuja y Alpine retrasa mostrar u ocultar elementos; no es un fallo de la app (se comprobó forzando el dibujado).

## Notas de la Fase 8

- Verificado: 470 pruebas automáticas (lector de ingredientes, raciones, lista de la compra, imágenes con eliminación de EXIF/GPS, permisos de fotos) y recorrido en el navegador sobre una copia aparte: raciones ajustadas, ingredientes a la lista de la compra, subida real de una foto (reducida a 1600 px, WEBP, entregada solo con permiso).
- Fotos (ADR-021): JPG/PNG/WEBP hasta 10 MB, se reprocesan con Pillow sin metadatos y se sirven por vistas que comprueban permisos. Foto de perfil visible solo para quien comparte hogar.
- Pendiente de comprobar a mano en el navegador: subir la foto de perfil (cubierta por pruebas automáticas).

## Acceso desde fuera de casa (2026-11-16)

- Tailscale (ADR-022): script de configuración de un clic, HTTPS con certificado válido, cookies seguras, app instalable con aviso "sin conexión" y arranque automático opcional. Guía: [acceso-remoto.md](acceso-remoto.md).
- Verificado: 480 pruebas automáticas (configuración de Tailscale simulada, service worker y página sin conexión públicos). Página sin conexión revisada en móvil y modo oscuro.
- Pendiente de comprobar en un móvil real: instalación de la app y aviso sin conexión (el navegador integrado del entorno de desarrollo no admite service workers).

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
| PWA instalable | 1 (manifest) · HTTPS con Tailscale (ADR-022) |
| Gestión de archivos e imágenes | 2 (URL) · 8 (subida) |
| Notificaciones internas, buscador global, exportación | 9 |
