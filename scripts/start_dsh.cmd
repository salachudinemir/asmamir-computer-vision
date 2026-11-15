@echo off
setlocal EnableExtensions
rem Deepseek harness at Windows login. Hidden. No camera window.
powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0start_dsh.ps1" %*
exit /b %ERRORLEVEL%
