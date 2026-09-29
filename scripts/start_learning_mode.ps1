param(
    [ValidateSet("general", "boot")]
    [string]$Mode = "general",
    [int]$Minutes = 5,
    [ValidateSet("general", "hero-inspection")]
    [string]$Scenario = "general",
    [string]$Domain = "general",
    [switch]$DisableNetworkObservation
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$toolPath = if ($Mode -eq "boot") {
    Join-Path $repoRoot "tools\learn_boot_click_elements.py"
} else {
    Join-Path $repoRoot "tools\learn_general_click_elements.py"
}

. "$PSScriptRoot\workstation-profile.ps1"
$pythonCommand = Get-DdProjectPython -ProjectRoot $repoRoot
$seconds = [Math]::Max(10, $Minutes * 60)
$invocationArgs = @()
$invocationArgs += $pythonCommand.PrefixArgs
$invocationArgs += $toolPath
if ($Mode -ne "boot") {
    $invocationArgs += @("--seconds", $seconds, "--scenario", ($Scenario -replace "-", "_"), "--domain", $Domain)
}
if ($DisableNetworkObservation) {
    $invocationArgs += "--no-network-observation"
}

$quotedArgs = ($invocationArgs | ForEach-Object { ConvertTo-DdPowerShellLiteral -Value ([string]$_) }) -join " "
$command = "Set-Location -LiteralPath $(ConvertTo-DdPowerShellLiteral -Value $repoRoot); Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue; Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue; & $(ConvertTo-DdPowerShellLiteral -Value $pythonCommand.Path) $quotedArgs"
Start-DdElevatedPowerShell -Command $command -WorkingDirectory $repoRoot -KeepOpen
