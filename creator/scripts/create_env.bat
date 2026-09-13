@echo off
setlocal
rem Use the inbox Windows PowerShell 5.1. Policy applies to this process only.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_env.ps1" %*
exit /b %ERRORLEVEL%
