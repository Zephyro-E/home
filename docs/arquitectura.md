# Arquitectura

> Decisiones justificadas en [decisiones.md](decisiones.md).

## Visión general

Monolito modular en **Django**. El servidor genera el HTML; **HTMX** actualiza fragmentos de página sin recargarla (mover tareas, votar, marcar productos) y **Alpine.js** cubre pequeñas interacciones locales (menús, hojas inferiores, avisos de "Deshacer").

```
Navegador (móvil / PC)
   │  HTML + HTMX + Alpine.js + Tailwind
   ▼
Waitress (servidor WSGI) ──► Django
                               ├─ core        usuarios, hogares, permisos, invitaciones, archivos
                               ├─ shopping    lista de la compra + deseos (votos, comentarios)
                               ├─ tasks       tablero de tareas (SortableJS para arrastrar)
                               ├─ events      calendario: eventos, repeticiones, tareas proyectadas
                               ├─ media       películas y series
                               ├─ places      sitios que visitar
                               ├─ finance     cuentas, categorías, movimientos (repartos en la fase 7)
                               └─ recipes     recetario                            (fase 8)
                               ▼
                           SQLite (WAL)  +  carpeta media/ (imágenes subidas)
```

## Stack

| Pieza | Tecnología |
|---|---|
| Lenguaje | Python 3.13 (fijado con **uv**) |
| Framework | Django 5.2 LTS |
| Interactividad | HTMX + Alpine.js (archivos estáticos locales, sin CDN) |
| Estilos | Tailwind CSS (binario independiente, sin Node.js) |
| Iconos | Lucide (SVG) |
| Base de datos | SQLite (modo WAL); PostgreSQL opcional en servidor |
| Contraseñas | Argon2id |
| Servidor | `runserver` en desarrollo · Waitress + WhiteNoise en casa |
| Pruebas | pytest + pytest-django; Playwright (Python) para E2E |
| Calidad | ruff (lint + formato) |
| CI | GitHub Actions (lint + pruebas) |

## Estructura de directorios prevista

```
Hogar/
├─ config/                ajustes Django (settings, urls, wsgi)
├─ apps/
│  ├─ core/               usuarios, hogares, permisos, middleware, mixins
│  └─ <módulo>/           models.py · views.py · forms.py · services.py · urls.py
│     ├─ templates/<módulo>/
│     └─ tests/
├─ templates/             base, componentes reutilizables (partials)
├─ static/                css, js (htmx, alpine), iconos, manifest PWA
├─ locale/en/             traducciones al inglés
├─ scripts/               arrancar, copia de seguridad, restaurar
├─ docs/                  esta documentación
├─ data/                  (ignorado en Git) base de datos, media, copias
├─ pyproject.toml · uv.lock
└─ README.md · CHANGELOG.md · CLAUDE.md
```

## Convenciones de cada módulo

- **models.py**: los modelos de dominio heredan de `HouseholdOwnedModel` (`household`, `owner`, `visibility`, `created_at`, `updated_at`).
- **services.py**: la lógica de negocio (cambios de estado, cálculos). Las vistas no contienen reglas de negocio.
- **views.py**: siempre con los *mixins* de autorización; los querysets siempre parten de `Model.objects.visible_to(user, household)`.
- **templates**: una plantilla de página y *partials* para los fragmentos que actualiza HTMX.
- **tests/**: como mínimo, pruebas de autorización (otro miembro, otro hogar, anónimo) y de la lógica de servicios.

## Seguridad

- Sesiones de Django en servidor con cookie `HttpOnly`, `SameSite=Lax`; `Secure` cuando haya HTTPS.
- CSRF activo (HTMX envía el token automáticamente desde la plantilla base).
- Contraseñas Argon2id; límite de intentos de inicio de sesión.
- Archivos subidos: tipos permitidos, tamaño máximo, reprocesado con Pillow (elimina EXIF) y servidos solo mediante una vista que comprueba permisos.
- Secretos en `.env` (nunca en Git). **El repositorio es público**: jamás se suben datos, base de datos ni copias.
- Acceso inicial solo desde la red de casa. Acceso exterior, si se desea, mediante VPN (Tailscale), no abriendo puertos del router.

## Copias de seguridad

- `manage.py backup` copia la base de datos en caliente (API de *backup* de SQLite) y comprime `media/` en `data/backups/AAAAMMDD-HHMMSS/`. Se conservan las 30 más recientes (`HOGAR_BACKUP_KEEP`).
- `scripts/servir.bat` hace una copia cada vez que arranca; `scripts/programar-copia.bat` programa una diaria en el Programador de tareas de Windows.
- `manage.py restore <copia>` (o `scripts/restaurar.bat`) comprueba la integridad, guarda antes el estado actual (`…-antes-de-restaurar`) y restaura. La app debe estar parada.
- Recomendado: copiar periódicamente `data/backups/` fuera del PC (disco externo o nube).

## Exportación

Prevista en la fase 9: exportación por módulo a CSV/JSON.
