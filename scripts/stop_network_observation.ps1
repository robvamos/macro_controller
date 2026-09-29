[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
. "$PSScriptRoot\workstation-profile.ps1"
$pythonCommand = Get-DdProjectPython -ProjectRoot $projectRoot
$runtimeDir = Get-DdWorkstationSetting -ProjectRoot $projectRoot -Name "runtimeDir" -PythonCommand $pythonCommand
$pidPath = Join-Path $runtimeDir "network_observation\active.pid"

if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Host "Nessuna sessione di osservazione risulta attiva."
    exit 0
}

$proxyPid = Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue
if ($proxyPid -and (Get-Process -Id $proxyPid -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $proxyPid
    Wait-Process -Id $proxyPid -Timeout 10 -ErrorAction SilentlyContinue
    Write-Host "Sessione proxy arrestata (PID $proxyPid)."
}
Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
