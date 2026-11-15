@echo off
REM Prepara el acceso desde fuera de casa con Tailscale (ver docs/acceso-remoto.md).
REM Antes: instala Tailscale (https://tailscale.com/download), entra con tu cuenta y
REM activa los certificados HTTPS en https://login.tailscale.com/admin/dns
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
uv run python manage.py tailscale configurar
echo.
echo Si todo ha ido bien, cierra y vuelve a abrir scripts\servir.bat.
pause
