@echo off
setlocal EnableExtensions
rem Asmamir at Windows login. No admin.
rem Start Hermes on 127.0.0.1:8642 only when /health is down,
rem then the Deepseek harness (ollama launch dsh) if it is not already running,
rem then one app.py. Does not open a second camera window. Does not bind port 3080.

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PY=%ROOT%\venv\Scripts\python.exe"
set "APP=%ROOT%\app.py"
set "HERMES=%LOCALAPPDATA%\hermes\gateway-service\Hermes_Gateway.vbs"
set "LOGDIR=%LOCALAPPDATA%\asmamir"
set "LOG=%LOGDIR%\login-start.log"

if /I "%~1"=="--dry" (
  echo ROOT=%ROOT%
  echo PY=%PY%
  echo APP=%APP%
  echo HERMES=%HERMES%
  echo Health=http://127.0.0.1:8642/health
  echo Deepseek=ollama launch dsh
  echo Port 3080 is not bound.
  curl.exe -fsS --max-time 2 "http://127.0.0.1:8642/health" >nul 2>&1
  if errorlevel 1 (echo Hermes health: down. Would start the gateway.) else (echo Hermes health: up. Would leave the gateway alone.)
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dsh.ps1" -DryRun
  echo Would start app.py only if it is not already running. No extra camera window.
  exit /b 0
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo %DATE% %TIME% Asmamir login start. Hermes 8642, then ollama launch dsh, then one app.py.>> "%LOG%"

curl.exe -fsS --max-time 2 "http://127.0.0.1:8642/health" >nul 2>&1
if not errorlevel 1 goto :dsh
echo %DATE% %TIME% Hermes health is down.>> "%LOG%"
if not exist "%HERMES%" goto :dsh
echo %DATE% %TIME% Starting Hermes gateway.>> "%LOG%"
start "" wscript.exe "%HERMES%"
set "TRIES=0"

:wait
set /a TRIES+=1
if %TRIES% GTR 20 goto :dsh
ping -n 2 127.0.0.1 >nul
curl.exe -fsS --max-time 2 "http://127.0.0.1:8642/health" >nul 2>&1
if errorlevel 1 goto :wait
echo %DATE% %TIME% Hermes API is up.>> "%LOG%"

:dsh
call "%~dp0start_dsh.cmd"

:app
if not exist "%PY%" (
  echo %DATE% %TIME% Python is missing: %PY%>> "%LOG%"
  exit /b 1
)
powershell.exe -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like '*asmamir_comvi*app.py*' }) { exit 10 }"
if errorlevel 10 (
  echo %DATE% %TIME% app.py is already running.>> "%LOG%"
  exit /b 0
)
echo %DATE% %TIME% Starting app.py>> "%LOG%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%PY%' -ArgumentList 'app.py' -WorkingDirectory '%ROOT%' -WindowStyle Hidden"
exit /b 0
