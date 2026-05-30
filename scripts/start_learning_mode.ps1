param(
    [ValidateSet("general", "boot")]
    [string]$Mode = "general",
    [int]$Minutes = 5
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$toolPath = if ($Mode -eq "boot") {
    Join-Path $repoRoot "tools\\learn_boot_click_elements.py"
} else {
    Join-Path $repoRoot "tools\\learn_general_click_elements.py"
}

$seconds = [Math]::Max(10, $Minutes * 60)
$python = if (Test-Path "F:\phyton3.131\python.exe") {
    "F:\phyton3.131\python.exe"
} else {
    "py"
}
$arguments = if ($Mode -eq "boot") {
    @($toolPath)
} else {
    @($toolPath, "--seconds", $seconds)
}

Start-Process -Verb RunAs -FilePath "powershell.exe" -ArgumentList @(
    "-NoExit",
    "-Command",
    ("Set-Location '{0}'; & '{1}' {2}" -f $repoRoot, $python, (($arguments | ForEach-Object { "'$_'" }) -join ' '))
) -WorkingDirectory $repoRoot
