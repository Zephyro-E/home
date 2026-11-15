@echo off
REM Sirve Hogar para usarla en casa (PC y moviles de la misma red): http://IP-DEL-PC:8000
REM La primera vez, Windows preguntara si permite el acceso en la red: elige "Redes privadas".
REM Al arrancar se hace una copia de seguridad automatica.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set HOGAR_DEBUG=0
if not defined HOGAR_ALLOWED_HOSTS set HOGAR_ALLOWED_HOSTS=*
uv run python manage.py backup
uv run python manage.py migrate
uv run python manage.py tailwind build
uv run python manage.py collectstatic --noinput
echo.
echo Hogar disponible en http://localhost:8000 (Ctrl+C para parar)
if exist .env for /f "tokens=2 delims==" %%u in ('findstr /b "HOGAR_CSRF_TRUSTED_ORIGINS=" .env') do echo Desde fuera de casa (Tailscale): %%u
uv run waitress-serve --listen=*:8000 config.wsgi:application
