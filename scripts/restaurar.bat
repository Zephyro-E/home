@echo off
REM Restaura una copia de seguridad. PARA LA APLICACION ANTES (cierra servir.bat / arrancar.bat).
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
echo Copias disponibles (la mas reciente arriba):
uv run python manage.py backup --list
echo.
set /p COPIA="Escribe el nombre de la copia a restaurar: "
if "%COPIA%"=="" exit /b 1
uv run python manage.py restore "%COPIA%"
pause
