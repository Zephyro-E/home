# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

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
