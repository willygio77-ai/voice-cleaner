@echo off
setlocal enabledelayedexpansion
title Build Voice Cleaner Desktop (PyInstaller)

echo ======================================================================
echo    Voice Cleaner Desktop - Compilazione Pacchetto Windows (--onedir)
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Verifica virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creazione dell'ambiente virtuale con Python 3.11...
    where uv >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        uv venv .venv --python 3.11
    ) else (
        py -3.11 -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" (
        echo ERRORE: Impossibile creare il virtual environment. Assicurati che Python 3.11 o uv sia installato.
        pause
        exit /b 1
    )
) else (
    echo [1/5] Virtual environment rilevato in .venv.
)

:: 2. Installazione/Verifica dipendenze
echo [2/5] Verifica e installazione dipendenze da requirements.txt...
where uv >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    uv pip install -r requirements.txt --python ".\.venv\Scripts\python.exe"
) else (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
if %ERRORLEVEL% NEQ 0 (
    echo ERRORE nell'installazione delle dipendenze.
    pause
    exit /b 1
)

:: Patch di compatibilità per PyTorch su PyInstaller (risolve NameError '_C')
".venv\Scripts\python.exe" -c "p = r'.venv\Lib\site-packages\torch\__init__.py'; c = open(p, encoding='utf-8').read(); c = c.replace('if TYPE_CHECKING:\n    import torch._C as _C', 'try:\n    import torch._C as _C\nexcept Exception:\n    pass'); open(p, 'w', encoding='utf-8').write(c)"

:: 3. Verifica modelli offline e binari FFmpeg
echo [3/5] Controllo modelli DeepFilterNet e binari FFmpeg inclusi...
if not exist "models\DeepFilterNet3\config.ini" (
    echo Copia del modello DeepFilterNet3 in corso...
    mkdir "models\DeepFilterNet3" 2>nul
    mkdir "models\DeepFilterNet3\checkpoints" 2>nul
    copy /y "%LOCALAPPDATA%\DeepFilterNet\DeepFilterNet\Cache\DeepFilterNet3\config.ini" "models\DeepFilterNet3\" >nul
    copy /y "%LOCALAPPDATA%\DeepFilterNet\DeepFilterNet\Cache\DeepFilterNet3\checkpoints\model_120.ckpt.best" "models\DeepFilterNet3\checkpoints\" >nul
)

if not exist "bin\ffmpeg.exe" (
    echo Ricerca e copia del binario FFmpeg...
    mkdir "bin" 2>nul
    for /r ".venv" %%f in (ffmpeg*.exe) do (
        copy /y "%%f" "bin\ffmpeg.exe" >nul
        goto :ffmpeg_found
    )
    :ffmpeg_found
)

:: 4. Generazione icona se mancante
if not exist "assets\icon.ico" (
    echo [4/5] Generazione asset grafici...
    mkdir "assets" 2>nul
    ".venv\Scripts\python.exe" -c "from PIL import Image, ImageDraw; img = Image.new('RGBA', (256, 256), (37, 99, 235, 255)); img.save('assets/icon.ico')"
) else (
    echo [4/5] Asset grafici pronti.
)

:: 5. Esecuzione PyInstaller
echo [5/5] Compilazione eseguibile con PyInstaller (voice_cleaner.spec)...
".venv\Scripts\pyinstaller.exe" --noconfirm voice_cleaner.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo ERRORE: La compilazione con PyInstaller e fallita.
    echo ======================================================================
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo    COMPILAZIONE COMPLETATA CON SUCCESSO!
echo    Eseguibile generato in:
echo    %~dp0dist\VoiceCleaner\VoiceCleaner.exe
echo ======================================================================
echo.
pause
