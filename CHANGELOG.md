# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

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
