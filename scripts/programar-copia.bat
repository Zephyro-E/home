@echo off
REM Programa una copia de seguridad diaria a las 21:00 en el Programador de tareas de Windows.
REM Si el PC esta apagado a esa hora, se hara al encenderlo. Para quitarla:
REM   schtasks /delete /tn "Hogar - copia diaria" /f
schtasks /create /tn "Hogar - copia diaria" /sc daily /st 21:00 /tr "\"%~dp0copia.bat\"" /f
powershell -NoProfile -Command "Set-ScheduledTask -TaskName 'Hogar - copia diaria' -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable)" >nul
echo Copia diaria programada.
pause
