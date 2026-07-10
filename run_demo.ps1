$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Missing .venv. Create it first with:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Set-Location $ProjectRoot

$Port = if ($env:VINSTROKE_STREAMLIT_PORT) { $env:VINSTROKE_STREAMLIT_PORT } else { "8502" }

Write-Host "Starting VinStroke-ECG Streamlit demo..."
Write-Host "Project: $ProjectRoot"
Write-Host "URL: http://127.0.0.1:$Port"

& $PythonExe -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port $Port
