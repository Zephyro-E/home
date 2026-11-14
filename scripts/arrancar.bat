@echo off
REM Arranca Hogar en modo desarrollo: http://localhost:8000
REM Recompila los estilos automaticamente al guardar cambios.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set HOGAR_DEBUG=1
uv run python manage.py migrate
uv run python manage.py tailwind runserver
