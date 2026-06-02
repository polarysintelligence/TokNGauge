# TokNGauge - Windows launcher
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$port = if ($env:TOKNGAUGE_PORT) { [int]$env:TOKNGAUGE_PORT } else { 8770 }

# Free the port if something is listening on it
$lines = netstat -ano | Select-String ":\b$port\b\s.*LISTENING"
foreach ($line in $lines) {
    $parts = $line.ToString().Trim() -split '\s+'
    $procId = $parts[-1]
    if ($procId -match '^\d+$' -and [int]$procId -ne 0) {
        Write-Host "Freeing port $port (killing PID $procId)"
        Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
    }
}
if ($lines) { Start-Sleep -Milliseconds 500 }

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# Recreate the venv if it's missing or was created on another OS (e.g. Linux,
# in which case it has bin/ instead of Scripts/ and python.exe is absent).
if (-not (Test-Path $venvPython)) {
    if (Test-Path ".venv") {
        Write-Host "Existing .venv is not a Windows virtualenv - recreating..."
        Remove-Item -Recurse -Force ".venv"
    }
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
& $venvPython -m pip install -q --upgrade pip
& $venvPython -m pip install -q -r requirements.txt

$env:TOKNGAUGE_PORT = "$port"
Write-Host "Starting TokNGauge on http://localhost:$port ..."
& $venvPython server.py
