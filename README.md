# Hogar

Aplicación web para gestionar la vida cotidiana de un hogar: lista de la compra y deseos, tareas, calendario, finanzas, recetas, sitios que visitar y películas/series. Pensada para usarse desde el móvil y el ordenador, compartida entre los miembros del hogar y con información personal privada.

> **Estado:** Fases 0–8 terminadas (todos los módulos previstos). Siguiente: Fase 9 (buscador, notificaciones, exportación, recuperación de contraseña). Ver [docs/roadmap.md](docs/roadmap.md). Ver [docs/roadmap.md](docs/roadmap.md).

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

## Puesta en marcha (Windows)

**Requisito único:** [uv](https://docs.astral.sh/uv/). Se instala una vez desde PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

uv descarga automáticamente la versión correcta de Python y las librerías del proyecto. La primera ejecución también descarga el compilador de estilos de Tailwind.

| Para… | Doble clic en / ejecuta |
|---|---|
| **Desarrollar** (recarga al guardar cambios) | `scripts\arrancar.bat` → http://localhost:8000 |
| **Usar la app en casa** (PC y móviles de la misma red) | `scripts\servir.bat` → http://IP-DEL-PC:8000 |

La primera vez que se use `servir.bat`, Windows preguntará si permite el acceso en la red: elige **Redes privadas**.

**Primer arranque:** la app abre un asistente para crear tu cuenta y tu hogar. Después, en *Hogar y miembros*, crea un enlace de invitación para cada persona.

## Copias de seguridad

| Para… | Doble clic en |
|---|---|
| Hacer una copia ahora | `scripts\copia.bat` |
| Programar una copia diaria (21:00) | `scripts\programar-copia.bat` (una sola vez) |
| Restaurar una copia (con la app parada) | `scripts\restaurar.bat` |

`servir.bat` hace además una copia cada vez que arranca. Las copias están en `data\backups\` (se guardan las 30 últimas); conviene copiar esa carpeta de vez en cuando a un disco externo o a la nube.

Los datos se guardan en la carpeta `data/` (base de datos, registros y clave secreta, que se genera sola). La configuración opcional se describe en `.env.example`.

## Comandos útiles

```bash
uv run pytest                        # pruebas automáticas
uv run ruff check . && uv run ruff format .   # revisar y formatear el código
uv run python manage.py changepassword correo@ejemplo.com   # restablecer una contraseña olvidada
uv run python manage.py tailwind build        # recompilar estilos
uv run python manage.py translations update   # extraer textos nuevos para traducir
```

## Privacidad

Este repositorio es público y contiene solo código y documentación. Los datos del hogar (base de datos, imágenes, copias de seguridad, `.env`) viven en la carpeta `data/` y nunca se suben a Git.
