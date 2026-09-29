@echo off
setlocal
pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_app.ps1"
set "APP_EXIT_CODE=%errorlevel%"
popd
exit /b %APP_EXIT_CODE%
