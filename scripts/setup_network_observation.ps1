[CmdletBinding()]
param(
    [string]$PythonVersion = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
. "$PSScriptRoot\workstation-profile.ps1"
$pythonCommand = Get-DdProjectPython -ProjectRoot $projectRoot
$requirements = Join-Path $projectRoot "requirements-network-observation.txt"
$venvRoot = Get-DdWorkstationSetting -ProjectRoot $projectRoot -Name "networkObserverDir" -PythonCommand $pythonCommand
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$mitmdump = Join-Path $venvRoot "Scripts\mitmdump.exe"

if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw "Requisiti osservatore non trovati: $requirements"
}

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    if ($PythonVersion) {
        $versionArgs = @()
        $versionArgs += $pythonCommand.PrefixArgs
        $versionArgs += "--version"
        $version = & $pythonCommand.Path @versionArgs
        if ($version -notmatch [regex]::Escape($PythonVersion)) {
            throw "Il runtime Python del profilo non corrisponde a $PythonVersion."
        }
    }
    $venvArgs = @()
    $venvArgs += $pythonCommand.PrefixArgs
    $venvArgs += @("-m", "venv", $venvRoot)
    & $pythonCommand.Path @venvArgs
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
