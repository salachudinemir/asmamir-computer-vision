# Start Asmamir at Windows login, without admin.
# Hermes API on 127.0.0.1:8642 only if /health is down,
# then ollama launch dsh if it is not already running, then one app.py.
# Does not open a second camera window. Does not bind port 3080.

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "venv\Scripts\python.exe"
$App = Join-Path $Root "app.py"
$HermesVbs = Join-Path $env:LOCALAPPDATA "hermes\gateway-service\Hermes_Gateway.vbs"
$HealthUrl = "http://127.0.0.1:8642/health"
$LogDir = Join-Path $env:LOCALAPPDATA "asmamir"
$LogFile = Join-Path $LogDir "login-start.log"

function Write-StartLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    if ($DryRun) { return }
    try {
        if (-not (Test-Path $LogDir)) {
            New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        }
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    } catch {
        Write-Host "Could not write $LogFile"
    }
}

function Test-HermesHealth {
    try {
        $request = [System.Net.HttpWebRequest]::Create($HealthUrl)
        $request.Timeout = 1500
        $request.Method = "GET"
        $response = $request.GetResponse()
        $response.Close()
        return $true
    } catch {
        return $false
    }
}

function Test-AppRunning {
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'"
    } catch {
        return $false
    }
    foreach ($proc in $procs) {
        $line = [string]$proc.CommandLine
        if ($line -like "*asmamir_comvi*app.py*") {
            return $true
        }
    }
    return $false
}

Write-StartLog "Asmamir login start. Hermes 8642, then ollama launch dsh, then one app.py."

if (Test-HermesHealth) {
    Write-StartLog "Hermes API is already up at $HealthUrl."
} elseif (-not (Test-Path $HermesVbs)) {
    Write-StartLog "Hermes gateway launcher is missing: $HermesVbs. Chat/look will use Ollama if Hermes stays down."
} elseif ($DryRun) {
    Write-StartLog "Would start Hermes gateway: $HermesVbs"
} else {
    Write-StartLog "Starting Hermes gateway for $HealthUrl."
    Start-Process -FilePath "$env:SystemRoot\System32\wscript.exe" -ArgumentList @($HermesVbs) -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(25)
    $up = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        if (Test-HermesHealth) {
            $up = $true
            break
        }
    }
    if ($up) {
        Write-StartLog "Hermes API is up at $HealthUrl."
    } else {
        Write-StartLog "Hermes API did not answer. The camera app still starts. Chat/look falls through to Ollama."
    }
}

$Dsh = Join-Path $Root "scripts\start_dsh.ps1"
if (Test-Path $Dsh) {
    if ($DryRun) {
        & $Dsh -DryRun
    } else {
        & $Dsh
    }
}

if (-not (Test-Path $Python)) {
    Write-StartLog "Python is missing: $Python"
    exit 1
}
if (Test-AppRunning) {
    Write-StartLog "app.py is already running. Leaving that window alone."
    exit 0
}
if ($DryRun) {
    Write-StartLog "Would start: $Python $App"
    exit 0
}

Write-StartLog "Starting $Python app.py"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath $Python -ArgumentList @("app.py") -WorkingDirectory $Root -WindowStyle Hidden
exit 0
