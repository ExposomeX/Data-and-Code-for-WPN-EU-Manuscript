@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup.ps1"
set "WPN_SETUP_EXIT=%ERRORLEVEL%"
pause
exit /b %WPN_SETUP_EXIT%
