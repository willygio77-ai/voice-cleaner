@echo off
title Voice Cleaner - Rimozione Rumore Vocale
cd /d "C:\Antigravity\Audio"
echo Avvio di Voice Cleaner in corso...
".venv\Scripts\python.exe" app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Si e verificato un errore durante l'esecuzione.
    pause
)
