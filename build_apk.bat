@echo off
setlocal
echo ===================================================
echo     Voice Cleaner - Compilazione APK Android
echo ===================================================
echo.

set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "ANDROID_HOME=C:\tmp\roi-android-toolchain\sdk"

cd /d "%~dp0android"

echo Compilazione con Gradle in corso...
call .\gradlew.bat assembleDebug --no-daemon

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo  APK COMPILATO CON SUCCESSO!
    echo ===================================================
    copy /Y "app\build\outputs\apk\debug\app-debug.apk" "..\VoiceCleaner.apk" >nul
    echo File salvato in: %~dp0VoiceCleaner.apk
) else (
    echo.
    echo ERRORE durante la compilazione dell'APK.
)

pause
