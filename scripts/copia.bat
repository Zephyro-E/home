@echo off
REM Crea una copia de seguridad en data\backups\ (se conservan las 30 mas recientes).
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
uv run python manage.py backup
