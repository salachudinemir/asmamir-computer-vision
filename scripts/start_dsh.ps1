# Deepseek harness at Windows login. No camera window. No port 3080.
# Starts "ollama launch dsh" only when that process is not already running.

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"
$Ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
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

function Test-DshRunning {
    try {
        $procs = Get-CimInstance Win32_Process
    } catch {
        return $false
    }
    foreach ($proc in $procs) {
        $line = [string]$proc.CommandLine
        if ($line -match 'launch\s+dsh' -or $line -match 'deepseek-harness') {
            return $true
        }
    }
    return $false
}

if (Test-DshRunning) {
    Write-StartLog "Deepseek harness is already running. Leaving it alone."
    exit 0
}
if (-not (Test-Path $Ollama)) {
    Write-StartLog "Ollama is missing: $Ollama"
    exit 1
}
if ($DryRun) {
    Write-StartLog "Would start: $Ollama launch dsh -y"
    exit 0
}

Write-StartLog "Starting ollama launch dsh."
Start-Process -FilePath $Ollama -ArgumentList @("launch", "dsh", "-y") -WindowStyle Hidden
exit 0
