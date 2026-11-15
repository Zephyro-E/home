# Usar Hogar desde fuera de casa (Tailscale)

Hogar sigue viviendo en el PC de casa. Tailscale crea una **red privada** entre tus dispositivos: el móvil "está en casa" aunque estés fuera, y nadie que no esté en tu red puede ni siquiera ver la página de entrada. Además da una dirección **HTTPS**, que permite instalar Hogar en el móvil como una app más.

Decisión técnica: [ADR-022](decisiones.md).

## 1. En el PC de casa (una sola vez)

1. **Instala Tailscale**: descárgalo de <https://tailscale.com/download> (Windows) e instálalo.
2. **Inicia sesión** cuando te lo pida (por ejemplo, con tu cuenta de Google). Quedará como un icono junto al reloj.
3. **Activa los certificados HTTPS** de tu red: entra en <https://login.tailscale.com/admin/dns>, comprueba que **MagicDNS** está activado y pulsa **Enable HTTPS** (en "HTTPS Certificates").
4. Haz doble clic en **`scripts\configurar-tailscale.bat`**. Al terminar mostrará la dirección de la app, del estilo:

   ```
   https://nombre-del-pc.tail1234.ts.net
   ```

5. **Cierra y vuelve a abrir `scripts\servir.bat`** para que la app aplique los cambios. Al arrancar mostrará también la dirección de Tailscale.

> Desde este momento, usa siempre esa dirección `https://…ts.net`, también en casa. En el propio PC sigue funcionando `http://localhost:8000`. La dirección antigua con la IP (`http://192.168…:8000`) deja de servir para entrar, porque las cookies de sesión pasan a ser solo seguras (HTTPS).

## 2. Que el PC esté siempre disponible

- **No lo dejes suspenderse**: Configuración de Windows → Sistema → Inicio/apagado y suspensión → "Suspender" → **Nunca** (al menos con el cargador conectado).
- **Arranque automático** (recomendado): haz doble clic una vez en **`scripts\arrancar-al-iniciar.bat`**. Hogar se abrirá solo cada vez que inicies sesión en Windows. Para quitarlo: `schtasks /delete /tn "Hogar - servidor" /f`.
- Tailscale ya arranca solo con Windows.

## 3. En cada móvil (o portátil)

1. Instala la app **Tailscale** (App Store o Google Play) y **actívala**.
2. Inicia sesión:
   - **Tú**: con la misma cuenta que usaste en el PC.
   - **Otras personas de casa**: invítalas desde <https://login.tailscale.com/admin/users> ("Invite users"), o comparte solo el PC desde <https://login.tailscale.com/admin/machines> (menú `…` del PC → "Share"), para que entren con su propia cuenta y solo vean ese equipo.
3. Abre la dirección `https://…ts.net` en el navegador y entra con tu cuenta de Hogar.
4. **Instálala como app**:
   - **Android (Chrome)**: menú `⋮` → **Instalar aplicación** (o "Añadir a pantalla de inicio").
   - **iPhone (Safari)**: botón **Compartir** → **Añadir a pantalla de inicio**.

Si el PC está apagado o Tailscale desconectado, la app instalada mostrará un aviso "No se puede conectar con Hogar" con un botón para reintentar.

## Preguntas frecuentes

- **¿Cuánto cuesta?** El plan personal de Tailscale es gratuito (en el momento de escribir esto, hasta 3 usuarios y 100 dispositivos). Compartir el PC con otras cuentas es otra forma de dar acceso sin ocupar usuarios.
- **¿Es seguro?** Sí: no se abre ningún puerto del router, el tráfico va cifrado y solo los dispositivos de tu red (o con los que compartes el PC) pueden llegar a la app. Aun así, cada persona necesita su usuario y contraseña de Hogar.
- **¿Y si cambio de PC o de nombre?** Vuelve a ejecutar `scripts\configurar-tailscale.bat`.
- **Dejar de publicar la app en Tailscale**: `uv run python manage.py tailscale quitar` y, en el archivo `.env`, borra las líneas `HOGAR_CSRF_TRUSTED_ORIGINS` y `HOGAR_HTTPS`.
- **Ver la configuración actual**: `uv run python manage.py tailscale estado`.
