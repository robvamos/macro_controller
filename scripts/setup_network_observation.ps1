[CmdletBinding()]
param(
    [string]$PythonVersion = "3.13"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$requirements = Join-Path $projectRoot "requirements-network-observation.txt"
$venvRoot = Join-Path $projectRoot ".tools\mitmproxy"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$mitmdump = Join-Path $venvRoot "Scripts\mitmdump.exe"

if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw "Requisiti osservatore non trovati: $requirements"
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        throw "Python Launcher (py.exe) non trovato. Installa Python $PythonVersion e riprova."
    }
    & $launcher.Source "-$PythonVersion" -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Creazione dell'ambiente mitmproxy non riuscita."
    }
}

# The desktop workspace may inject unrelated PDF packages through PYTHONPATH.
# Keep the optional proxy runtime self-contained inside this project.
$env:PYTHONPATH = $null
$env:PYTHONNOUSERSITE = "1"
& $venvPython -m pip install --requirement $requirements
if ($LASTEXITCODE -ne 0) {
    throw "Installazione delle dipendenze mitmproxy non riuscita."
}

& $mitmdump --version
if ($LASTEXITCODE -ne 0) {
    throw "Verifica mitmproxy non riuscita."
}

Write-Host "Osservatore installato in $venvRoot"
Write-Host "Nessuna CA e nessuna impostazione proxy di Windows sono state modificate."
