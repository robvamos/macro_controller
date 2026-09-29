param([switch]$Elevated)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
. "$PSScriptRoot\workstation-profile.ps1"

if (-not $Elevated) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $command = "& $(ConvertTo-DdPowerShellLiteral -Value $PSCommandPath) -Elevated"
        Start-DdElevatedPowerShell -Command $command -WorkingDirectory $projectRoot
        exit 0
    }
}

$pythonCommand = Get-DdProjectPython -ProjectRoot $projectRoot
$entrypoint = Join-Path $projectRoot "gui_macro_manager.py"
$invocationArgs = @()
$invocationArgs += $pythonCommand.PrefixArgs
$invocationArgs += $entrypoint
Set-Location -LiteralPath $projectRoot
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
& $pythonCommand.Path @invocationArgs
exit $LASTEXITCODE
