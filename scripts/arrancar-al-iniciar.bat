@echo off
REM Hace que Hogar arranque solo al iniciar sesion en Windows (abre servir.bat).
REM Util para usar la app desde fuera de casa: el PC solo tiene que estar encendido.
REM Para quitarlo:
REM   schtasks /delete /tn "Hogar - servidor" /f
schtasks /create /tn "Hogar - servidor" /sc onlogon /tr "\"%~dp0servir.bat\"" /f
echo Hogar arrancara solo al iniciar sesion en este PC.
pause
