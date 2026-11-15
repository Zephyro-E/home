# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.5.0] - 2026-11-15 · Fase 4: calendario

### Añadido
- Calendario con vistas de mes, semana y agenda (60 días), generadas en el servidor (ADR-018).
- Eventos con tipo (evento, cita, cumpleaños, celebración, viaje), lugar, participantes, día completo o con hora, de varios días, del hogar o personales.
- Repeticiones: cada día / semana / mes / año, cada N y hasta una fecha (RRULE, `python-dateutil`); conservan la hora con el cambio de horario.
- Los cumpleaños se marcan solos como día completo y anuales.
- Las tareas con fecha aparecen en el calendario sin duplicarse.
- Tareas recurrentes: al terminarlas se crea la siguiente con su nueva fecha.
- El aviso "Para hoy" del inicio incluye los eventos del día.
- 270 pruebas automáticas.

## [0.4.0] - 2026-11-15 · Fase 3: tareas

### Añadido
- Tablero de tareas Pendiente / En curso / Terminada con arrastrar y soltar (SortableJS, ADR-017) y botones Empezar / Terminar / Reabrir.
- Alta rápida desde el tablero; formulario completo con responsable, fecha límite, prioridad, estado, descripción y etiquetas.
- Tareas del hogar o personales (pasar de personal a compartida).
- Subtareas con progreso, comentarios y etiquetas de colores comunes al hogar.
- Filtros: todas, mías, sin responsable y por etiqueta.
- Avisos de fecha: vencida, hoy; widget "Para hoy" en el inicio.
- En el móvil y tablets, una columna cada vez con pestañas.
- 212 pruebas automáticas.

### Cambiado
- `templates/partials/field.html` pasa a ser un componente común de formularios.

## [0.3.0] - 2026-11-15 · Fase 2: compras

### Añadido
- Lista de la compra compartida: añadir sin recargar la página, cantidad opcional, marcar como comprado, quitar productos y "Quitar comprados". Un producto repetido no se duplica.
- Deseos personales (solo los ve su dueño) y propuestas comunes, con precio aproximado, prioridad, enlace a la tienda, imagen por enlace y descripción.
- Estados Pendiente / Aprobado / Comprado / Descartado (cualquier miembro en lo común), con quién y cuándo lo cambió.
- Votos a favor y en contra (uno por persona, modificable y retirable, visibles para el hogar) y comentarios.
- Pasar un deseo personal a propuesta común.
- Borrado con "Deshacer" durante 6 segundos (ADR-016).
- Widgets en el inicio: productos pendientes y propuestas por votar.
- Importes en céntimos con formato en euros (`apps/core/money.py`, filtro `euros`).
- 144 pruebas automáticas.

## [0.2.0] - 2026-11-14 · Fase 1: identidad y hogar

### Añadido
- Asistente de primer arranque: crea la primera cuenta y el hogar.
- Inicio y cierre de sesión por email, con bloqueo tras 5 intentos fallidos.
- Hogares, miembros con rol (administración/miembro) y color propio, cambio entre hogares.
- Invitaciones por enlace de un solo uso (caducan a los 7 días; solo se guarda su hash).
- Gestión del hogar: renombrar, cambiar roles, quitar miembros, salir (siempre queda alguien con administración).
- Patrón común de permisos para los módulos: hogar + dueño + visibilidad (`visible_to`).
- Perfil: nombre, email, idioma, tema (guardado también desde el botón de tema) y cambio de contraseña.
- Traducción completa al inglés y comando `translations` (sin GNU gettext).
- Copias de seguridad y restauración (`backup`, `restore`, scripts `copia`, `restaurar`, `programar-copia`); copia automática al arrancar `servir.bat`.
- Manifest PWA e iconos de la app.
- 66 pruebas automáticas.

### Cambiado
- Todas las páginas exigen sesión salvo las públicas marcadas explícitamente.

## [0.1.0] - 2026-11-14 · Fase 0: cimientos

### Añadido
- Proyecto Django 5.2 LTS gestionado con uv (Python 3.13 fijado).
- Usuario propio con inicio de sesión por email y contraseñas Argon2.
- Configuración por variables de entorno (`.env.example`), clave secreta autogenerada en `data/`.
- SQLite en modo WAL; registro de errores en `data/logs/hogar.log`.
- Plantilla base adaptable: barra lateral (escritorio), cabecera y barra inferior (móvil).
- Modo claro, oscuro o según el sistema, sin parpadeo al cargar.
- Tailwind CSS 4 (binario independiente), HTMX 2 (con token CSRF) y Alpine.js 3.
- Iconos Lucide y registro de módulos para el dashboard y la navegación.
- Dashboard inicial con los módulos previstos marcados como "próximamente".
- Idiomas español/inglés configurados (las traducciones llegan en la Fase 1).
- Scripts `arrancar.bat` (desarrollo) y `servir.bat` (uso en casa con Waitress).
- Pruebas con pytest (14), lint con ruff y CI en GitHub Actions.

### Documentación
- Requisitos, arquitectura, decisiones técnicas (ADR 001–012), modelo de datos, diseño UX/UI y roadmap.
