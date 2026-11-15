# Registro de decisiones técnicas (ADR)

Cada decisión relevante se registra aquí con su contexto, la alternativa elegida y sus consecuencias.
No se borran decisiones: si una cambia, se añade una nueva que la sustituye y se marca la antigua como *Sustituida*.

| ADR | Título | Estado | Fecha |
|-----|--------|--------|-------|
| 001 | Monolito modular | Aceptada | 2026-11-14 |
| 002 | Django + HTMX como stack principal | Aceptada | 2026-11-14 |
| 003 | SQLite ahora, PostgreSQL opcional en servidor | Aceptada | 2026-11-14 |
| 004 | Ejecución nativa en Windows; Docker al migrar a servidor | Aceptada | 2026-11-14 |
| 005 | Modelo de permisos: hogar + dueño + visibilidad | Aceptada | 2026-11-14 |
| 006 | Registro solo por invitación | Aceptada | 2026-11-14 |
| 007 | Importes en céntimos enteros, moneda única EUR | Aceptada | 2026-11-14 |
| 008 | Fechas en UTC con zona horaria del hogar | Aceptada | 2026-11-14 |
| 009 | Idiomas: español principal, inglés secundario | Aceptada | 2026-11-14 |
| 010 | Borrado definitivo con "Deshacer" de unos segundos | Aceptada | 2026-11-14 |
| 011 | Hogar activo en sesión, validado en cada petición | Aceptada | 2026-11-14 |
| 012 | Recurrencias con RRULE (RFC 5545) | Aceptada | 2026-11-14 |
| 013 | Traducciones con Babel en lugar de GNU gettext | Aceptada | 2026-11-14 |
| 014 | Avatar de iniciales; fotos con la gestión de archivos | Aceptada | 2026-11-14 |
| 015 | Todas las páginas exigen sesión por defecto | Aceptada | 2026-11-14 |
| 016 | "Deshacer": confirmación al salir de la página | Aceptada | 2026-11-15 |
| 017 | Arrastrar y soltar con SortableJS | Aceptada | 2026-11-15 |
| 018 | Calendario generado en el servidor (sin FullCalendar) | Aceptada | 2026-11-15 |
| 019 | Privacidad en finanzas: la cuenta manda | Aceptada | 2026-11-15 |

---

## ADR-001 · Monolito modular

**Contexto.** Aplicación para un hogar (2–5 personas), alojada en un PC doméstico y más adelante en un servidor particular.

**Decisión.** Un único proyecto Django con una *app* por módulo (`shopping`, `tasks`, `calendar`…), una sola base de datos y un solo proceso.

**Consecuencias.** Despliegue y copias de seguridad triviales. Los módulos se comunican mediante funciones Python, no por red. Si un módulo creciera mucho, sus fronteras (app propia, sin importar modelos internos de otras apps salvo a través de sus servicios) permitirían separarlo.

---

## ADR-002 · Django + HTMX como stack principal

**Contexto.** El propietario no programa: el desarrollo se hará mediante asistentes de IA ("vibe coding") y prefiere Python por legibilidad. Se necesita algo maduro, seguro por defecto y con pocas piezas.

**Alternativas consideradas.**
- *React + Fastify (TypeScript)*: propuesta inicial. Muy capaz, pero son dos aplicaciones (frontend y API), dos procesos de build y más superficie de errores para alguien que no programa.
- *Next.js*: complejidad del modelo servidor/cliente.
- *Laravel*: válido, pero PHP no es la preferencia.
- *Django + HTMX*: un solo lenguaje, HTML renderizado en servidor, interacciones dinámicas con HTMX sin escribir una SPA.

**Decisión.** Django (rama LTS 5.2) + plantillas Django + **HTMX** + **Alpine.js** (pequeñas interacciones) + **Tailwind CSS** compilado con el binario independiente (sin Node.js).

**Por qué encaja.** Django incluye de serie autenticación, sesiones, protección CSRF, migraciones, validación de formularios, internacionalización, panel de administración y un ORM que impide inyección SQL. Menos librerías = menos cosas que mantener y menos errores que la IA pueda introducir.

**Librerías complementarias previstas (se añaden cuando su fase lo requiera):** `django-htmx`, `argon2-cffi`, `Pillow`, `whitenoise`, `waitress` (servidor en Windows), `python-dateutil` (RRULE), `pytest-django`, `ruff`; SortableJS (kanban), Chart.js (gráficos). FullCalendar se descartó (ADR-018).

**Consecuencias.** Cambia la propuesta inicial (React + Fastify). No habrá API REST pública en las primeras fases: las vistas devuelven HTML. Si en el futuro se necesitara una app nativa o integraciones, se añadiría una API (Django Ninja o DRF) sobre los mismos servicios.

---

## ADR-003 · SQLite ahora, PostgreSQL opcional en servidor

**Contexto.** Un solo hogar, pocas personas usuarias, PC doméstico con Windows sin Docker instalado.

**Decisión.** SQLite (modo WAL) como base de datos. El código no usará funciones específicas de un motor, de modo que pasar a PostgreSQL sea un cambio de configuración más una migración de datos (`dumpdata`/`loaddata`).

**Consecuencias.** Cero instalación y copia de seguridad = copiar un archivo (con la API de *backup* de SQLite para hacerlo en caliente). SQLite es sobradamente suficiente para este volumen. Al migrar al servidor se decidirá si se mantiene SQLite o se pasa a PostgreSQL.

---

## ADR-004 · Ejecución nativa en Windows; Docker al migrar a servidor

**Contexto.** Docker Desktop no está instalado y añade complejidad (WSL2, recursos) que no aporta valor mientras la app vive en un único PC.

**Decisión.** En esta etapa la app se ejecuta con Python nativo, gestionado con **uv** (versiones de Python y dependencias reproducibles, fijadas en `uv.lock`). Para servirla en la red de casa se usa **Waitress** (servidor WSGI compatible con Windows). El `Dockerfile` y `compose.yaml` se crearán en la fase de migración al servidor.

**Consecuencias.** Arranque sencillo con un único comando. El requisito de "desplegable con Docker Compose" queda aplazado, no descartado. Todo seguirá versionado en Git; no habrá cambios manuales fuera del repositorio.

**Nota PWA/HTTPS.** Un móvil solo instala una PWA completa (service worker) si la web se sirve por HTTPS. En la red local por HTTP la app funcionará en el navegador del móvil, pero la instalación como PWA requerirá HTTPS. Opción preferida cuando llegue el momento: **Tailscale** (HTTPS automático y acceso seguro desde fuera de casa sin abrir puertos). Se decidirá en la Fase 1.

---

## ADR-005 · Modelo de permisos: hogar + dueño + visibilidad

**Decisión.** Todo elemento de un módulo pertenece a un hogar (`household`), tiene un dueño (`owner`) y una visibilidad (`private` / `shared`).

- Ver: un elemento `shared` lo ve cualquier miembro del hogar; uno `private`, **solo su dueño** (ni siquiera quien administra el hogar).
- Editar elementos compartidos: **cualquier miembro** (decisión del propietario).
- Cambiar estado de compras (aprobar, comprar, descartar): **cualquier miembro**.
- Roles del hogar: `admin` (gestiona miembros, invitaciones y configuración) y `member`.
- Toda comprobación se hace en el servidor mediante un *manager* común (`visible_to(user, household)`) y *mixins* de vista. Ningún queryset de dominio se construye sin ese filtro.
- Acceso a un elemento de otro hogar o privado ajeno → **404** (no se revela que existe).
- Cada vista tiene pruebas automáticas de autorización.

---

## ADR-006 · Registro solo por invitación

**Decisión.** No hay registro abierto. La primera cuenta (administración) se crea con un asistente de configuración inicial o comando. Los demás miembros entran con un enlace de invitación de un solo uso y caducidad limitada.

---

## ADR-007 · Importes en céntimos enteros, moneda única EUR

**Decisión.** Los importes se guardan como enteros en céntimos (`BigIntegerField`), nunca como coma flotante. Moneda única: euro. Repartos en puntos básicos (10 000 = 100 %); el céntimo sobrante del redondeo se asigna de forma determinista. Reparto por defecto del hogar **50/50 configurable**, con excepciones por gasto. Las transferencias internas son un tipo de movimiento propio, excluido de las estadísticas de ingresos y gastos.

---

## ADR-008 · Fechas en UTC con zona horaria del hogar

**Decisión.** `USE_TZ = True`. Los instantes se guardan en UTC y se muestran en la zona del hogar (por defecto `Europe/Madrid`). Eventos de día completo, cumpleaños y fechas límite sin hora se guardan como `date`, sin hora, para que no cambien de día con el horario de verano.

---

## ADR-009 · Idiomas: español principal, inglés secundario

**Decisión.** Internacionalización nativa de Django (gettext). Los textos se escriben **en español en el código** y se traducen al inglés en archivos `.po`. Así, si falta alguna traducción, el idioma principal nunca se ve afectado. Cada persona elige idioma en su perfil.

**Coste.** Bajo: envolver los textos en `{% translate %}` / `_()` y mantener un archivo de traducción. Sin dependencias extra.

---

## ADR-010 · Borrado definitivo con "Deshacer" de unos segundos

**Decisión.** Al borrar, el elemento desaparece de la interfaz y aparece un aviso con **Deshacer** durante ~6 segundos. Si no se deshace, se borra definitivamente en el servidor. No hay papelera.

**Implementación prevista.** El borrado real se envía al servidor al expirar el aviso (precisado en ADR-016: también al salir de la página). Si el envío no llega, el borrado no se produce (fallo seguro: el elemento sigue existiendo). Para elementos con muchos datos asociados se pedirá además confirmación explícita.

---

## ADR-011 · Hogar activo en sesión, validado en cada petición

**Decisión.** El hogar con el que se trabaja se guarda en la sesión. Un *middleware* comprueba en **cada petición** que la persona sigue siendo miembro y lo expone como `request.household`. Las URL quedan limpias (`/compras/`), y el selector de hogar solo aparece si se pertenece a más de uno.

---

## ADR-012 · Recurrencias con RRULE (RFC 5545)

**Decisión.** Tareas y eventos recurrentes guardan su regla en formato RRULE estándar y se expanden al consultar con `python-dateutil`. El calendario **proyecta** las tareas con fecha límite al leer, sin copiarlas como eventos, manteniendo la referencia al original.

---

## ADR-013 · Traducciones con Babel en lugar de GNU gettext

**Contexto.** Las herramientas de traducción de Django (`makemessages`, `compilemessages`) necesitan GNU gettext, que no viene con Windows.

**Decisión.** Comando propio `manage.py translations update|compile|check`, basado en Babel (Python puro, dependencia solo de desarrollo). Reconoce `_()`, `gettext()`, `gettext_lazy()`, `{% translate %}` y `{% blocktranslate %}` (reproduce cómo Django construye los textos de este último). Los `.po` y `.mo` se versionan, así que usar la app no requiere compilar nada.

**Consecuencias.** Una prueba automática falla si algún texto queda sin traducir o sin compilar. No se usan plurales ni contextos (`pgettext`) por ahora; si hicieran falta, se ampliaría el comando.

---

## ADR-014 · Avatar de iniciales; fotos con la gestión de archivos

**Decisión.** En la Fase 1 el avatar muestra las iniciales sobre el color del miembro en el hogar. La subida de fotos llegará con la gestión de archivos (Fase 8), que resolverá de una vez tamaño, formatos, eliminación de EXIF y acceso con permisos.

---

## ADR-015 · Todas las páginas exigen sesión por defecto

**Decisión.** Se activa `LoginRequiredMiddleware` de Django: cualquier vista nueva exige sesión salvo que se marque explícitamente con `@login_not_required` (hoy solo: entrada, asistente inicial, invitación y cambio de idioma). Olvidar proteger una vista deja de ser posible.

---

## ADR-016 · "Deshacer": confirmación al salir de la página

**Contexto.** ADR-010 preveía que, si se cerraba la pestaña antes de que expirase el aviso, el borrado no se produjera. En la práctica, borrar algo y pasar enseguida a otra pantalla de la app hacía que el elemento "resucitara", lo que resulta confuso.

**Decisión.** El aviso dura 6 segundos (`static/js/app.js`, store `undo`). El borrado pendiente se envía al servidor: al expirar el aviso, al empezar otro borrado, antes de cualquier petición HTMX de la página (para que la respuesta no vuelva a traer el elemento) y al salir de la página (`pagehide`, petición `keepalive`). Si el envío no llega (cierre brusco, sin red), el elemento simplemente sigue existiendo: el fallo sigue siendo seguro.

**Consecuencias.** Los borrados se hacen con un único componente reutilizable (`x-data="deletable"` con `data-delete-url`, `data-ids`, `data-undo-message` y, opcionalmente, `data-after-url`). Las vistas de borrado responden 204 cuando la petición lleva la cabecera `X-Undo-Commit`.

---

## ADR-017 · Arrastrar y soltar con SortableJS

**Decisión.** El tablero de tareas usa SortableJS 1.15.6 (MIT), copiado en `static/js/sortable.min.js` y cargado solo en esa página (sin CDN, como HTMX y Alpine). Se usa su modo propio de arrastre (`forceFallback`), que se comporta igual con ratón y en pantallas táctiles; en táctil hay que mantener pulsado un momento para no interferir con el desplazamiento.

**Funcionamiento.** Al soltar, se envía al servidor la columna de destino y el orden de esa columna; el servidor solo reordena las tareas que la persona puede ver y editar, y devuelve el tablero actualizado (HTMX). Como alternativa accesible y cómoda en el móvil, cada tarjeta tiene un botón para pasar a la columna siguiente (Empezar, Terminar, Reabrir).

---

## ADR-018 · Calendario generado en el servidor (sin FullCalendar)

**Contexto.** ADR-002 preveía FullCalendar para las vistas del calendario. Es una librería grande, pensada sobre todo para escritorio, y obliga a exponer los datos como JSON.

**Decisión.** Las vistas de mes, semana y agenda se generan en el servidor con plantillas de Django, como el resto de la aplicación. Las repeticiones se expanden al consultar (`apps/events/services.py`, `items_between`) con `python-dateutil`, en hora local para que un evento conserve su hora tras el cambio de horario. Las tareas con fecha límite se proyectan en el mismo listado sin copiarse.

**Consecuencias.** Menos JavaScript y la misma lógica de permisos que el resto. No hay arrastrar eventos para cambiarlos de hora (se editan con el formulario). El rango consultado está limitado (400 días) para que nunca se expandan series enormes.

**Nota.** La app se llama `apps/events` (el nombre `calendar` choca con el módulo estándar de Python), pero sus URL usan el espacio de nombres `calendar` y la ruta `/calendario/`.

---

## ADR-019 · Privacidad en finanzas: la cuenta manda

**Contexto.** En finanzas conviven cuentas comunes y personales, y un mismo movimiento puede tocar dos cuentas (transferencias). Si el saldo de una cuenta común dependiera de movimientos que no todos ven, no cuadraría.

**Decisión.**
- Cada cuenta es común (la ven y usan todos) o personal (solo su dueño). No se puede cambiar después.
- La visibilidad de un movimiento se calcula sola: es común si toca alguna cuenta común y personal si solo toca cuentas personales.
- Quien ve un movimiento común que toca una cuenta personal ajena ve "Cuenta personal de X", nunca el nombre ni el saldo de esa cuenta.
- Para crear, editar o borrar un movimiento hay que poder usar todas las cuentas que toca (además de la regla general de ADR-005).
- Los saldos se calculan con todos los movimientos de cada cuenta (inicial + ingresos − gastos ± transferencias). Las transferencias no cuentan en ingresos ni gastos del resumen (ADR-007).

**Consecuencias.** El saldo de una cuenta común es el mismo para todos los miembros. Los repartos de gastos entre personas (Fase 7) se apoyarán en estos movimientos comunes.
