@echo off
setlocal

cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

set "PY_CMD="
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo Python non trovato nel PATH.
    echo Installa Python oppure aggiungilo al PATH, poi riprova.
    pause
    exit /b 1
)

%PY_CMD% gui_macro_manager.py
set "APP_EXIT_CODE=%errorlevel%"

if not "%APP_EXIT_CODE%"=="0" (
    echo.
    echo L'applicazione si e' chiusa con codice errore %APP_EXIT_CODE%.
    pause
)

exit /b %APP_EXIT_CODE%
