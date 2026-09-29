[CmdletBinding()]
param(
    [string]$TargetProcess = "Doomsday",
    [int]$TargetPid = 0,
    [string]$ShortcutPath = "",
    [switch]$LaunchViaShortcut,
    [ValidateRange(10, 600)]
    [int]$LaunchTimeoutSeconds = 180,
    [ValidateRange(1, 120)]
    [int]$Minutes = 5,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
. "$PSScriptRoot\workstation-profile.ps1"
$pythonCommand = Get-DdProjectPython -ProjectRoot $projectRoot
$runtimeDir = Get-DdWorkstationSetting -ProjectRoot $projectRoot -Name "runtimeDir" -PythonCommand $pythonCommand
$observerDir = Get-DdWorkstationSetting -ProjectRoot $projectRoot -Name "networkObserverDir" -PythonCommand $pythonCommand
$mitmdump = Join-Path $observerDir "Scripts\mitmdump.exe"
$addon = Join-Path $projectRoot "tools\proxy\metadata_addon.py"
$runtimeRoot = Join-Path $runtimeDir "network_observation"
$confdir = Join-Path $runtimeRoot "mitmproxy-config"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionDir = Join-Path $runtimeRoot $timestamp
$eventsPath = Join-Path $sessionDir "events.jsonl"
$sessionPath = Join-Path $sessionDir "session.json"
$stdoutPath = Join-Path $sessionDir "proxy.stdout.log"
$stderrPath = Join-Path $sessionDir "proxy.stderr.log"
$pidPath = Join-Path $runtimeRoot "active.pid"

if (-not (Test-Path -LiteralPath $mitmdump)) {
    throw "mitmdump non trovato in $mitmdump. Esegui prima scripts\setup_network_observation.ps1."
}
if (-not (Test-Path -LiteralPath $addon)) {
    throw "Addon metadata-only non trovato in $addon"
}
$launcherUsed = $false
if ($TargetPid -le 0) {
    $target = Get-Process -Name $TargetProcess -ErrorAction SilentlyContinue |
        Sort-Object StartTime -Descending |
        Select-Object -First 1
    if (-not $target -and $LaunchViaShortcut) {
        if (-not $ShortcutPath) {
            $ShortcutPath = Get-DdWorkstationSetting -ProjectRoot $projectRoot -Name "gameShortcutPath" -PythonCommand $pythonCommand
        }
        if (-not $ShortcutPath) {
            $ShortcutPath = Join-Path $env:PUBLIC "Desktop\Doomsday.lnk"
        }
        if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) {
            throw "Collegamento launcher non trovato: $ShortcutPath"
        }
        Write-Host "Avvio richiesto tramite launcher: $ShortcutPath"
        Start-Process -FilePath $ShortcutPath
        $launcherUsed = $true
        $deadline = (Get-Date).AddSeconds($LaunchTimeoutSeconds)
        do {
            Start-Sleep -Milliseconds 250
            $target = Get-Process -Name $TargetProcess -ErrorAction SilentlyContinue |
                Sort-Object StartTime -Descending |
                Select-Object -First 1
        } while (-not $target -and (Get-Date) -lt $deadline)
    }
    if (-not $target) {
        throw "Il processo '$TargetProcess' non e in esecuzione. Usa il collegamento launcher oppure riprova con -LaunchViaShortcut."
    }
    $TargetPid = $target.Id
}
elseif (-not (Get-Process -Id $TargetPid -ErrorAction SilentlyContinue)) {
    throw "Il PID $TargetPid non e in esecuzione."
}
if (Test-Path -LiteralPath $pidPath) {
    $activePid = Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue
    if ($activePid -and (Get-Process -Id $activePid -ErrorAction SilentlyContinue)) {
        throw "Esiste gia una sessione di osservazione (PID $activePid)."
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null
New-Item -ItemType Directory -Path $confdir -Force | Out-Null

$session = [ordered]@{
    schema = "doomsday.network-observation-session.v1"
    started_at = (Get-Date).ToUniversalTime().ToString("o")
    target_process = $TargetProcess
    target_pid = $TargetPid
    launcher_shortcut = if ($launcherUsed) { $ShortcutPath } else { $null }
    launcher_requested = [bool]$LaunchViaShortcut
    launcher_used = $launcherUsed
    duration_minutes = $Minutes
    capture_mode = "local-process"
    capture_level = "metadata-only"
    tls_passthrough = $true
    ca_trusted = $false
    payloads_persisted = $false
    events_path = $eventsPath
}
$session | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $sessionPath -Encoding utf8

$arguments = @(
    "--mode", "local:$TargetPid",
    "--set", "confdir=$confdir",
    "--set", "dd_observation_output=$eventsPath",
    "--set", "dd_observation_tls_passthrough=true",
    "--quiet",
    "--scripts", $addon
)

Write-Host "Osservazione metadata-only del processo $TargetProcess (PID $TargetPid)"
Write-Host "TLS resta cifrato e viene inoltrato senza installare CA."
Write-Host "Sessione: $sessionDir"

if ($Foreground) {
    & $mitmdump @arguments
    exit $LASTEXITCODE
}

$process = Start-Process -FilePath $mitmdump -ArgumentList $arguments -WorkingDirectory $projectRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii
$endedEarly = $false
try {
    Wait-Process -Id $process.Id -Timeout ($Minutes * 60) -ErrorAction SilentlyContinue
    if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
        Stop-Process -Id $process.Id
        Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
    else {
        $endedEarly = $true
    }
}
finally {
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

$session["ended_at"] = (Get-Date).ToUniversalTime().ToString("o")
$process.Refresh()
$session["exit_code"] = $process.ExitCode
$session["status"] = if ($endedEarly -and $process.ExitCode -ne 0) { "failed" } else { "completed" }
$session | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $sessionPath -Encoding utf8
Write-Host "Osservazione conclusa: $eventsPath"
