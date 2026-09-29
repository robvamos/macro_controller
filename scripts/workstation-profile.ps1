function Get-DdBootstrapPython {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $configured = $env:CODEX_PYTHON_EXE
    if (-not $configured) {
        $configured = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    }
    if ($env:CODEX_PYTHON_EXE -and -not (Test-Path -LiteralPath $configured -PathType Leaf)) {
        throw "CODEX_PYTHON_EXE does not identify an existing Python executable."
    }
    if (Test-Path -LiteralPath $configured -PathType Leaf) {
        return @{ Path = $configured; PrefixArgs = @() }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{ Path = $python.Source; PrefixArgs = @() }
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        return @{ Path = $launcher.Source; PrefixArgs = @("-3") }
    }
    throw "Python non trovato. Aggiungilo al PATH o configura CODEX_PYTHON_EXE."
}

function Get-DdWorkstationSetting {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$PythonCommand
    )

    $settingsScript = Join-Path $ProjectRoot "workstation\settings.py"
    $invocationArgs = @()
    $invocationArgs += $PythonCommand.PrefixArgs
    $invocationArgs += @($settingsScript, "--get", $Name)
    $value = & $PythonCommand.Path @invocationArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Workstation settings are invalid. Run python workstation/settings.py for details."
    }
    return ($value | Out-String).Trim()
}

function Get-DdProjectPython {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $bootstrap = Get-DdBootstrapPython -ProjectRoot $ProjectRoot
    $configured = Get-DdWorkstationSetting -ProjectRoot $ProjectRoot -Name "pythonExe" -PythonCommand $bootstrap
    if ($configured) {
        if (-not (Test-Path -LiteralPath $configured -PathType Leaf)) {
            throw "The Python executable in the selected workstation profile is missing."
        }
        return @{ Path = $configured; PrefixArgs = @() }
    }
    return $bootstrap
}

function ConvertTo-DdPowerShellLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Start-DdElevatedPowerShell {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string]$WorkingDirectory,
        [switch]$KeepOpen
    )

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass")
    if ($KeepOpen) {
        $arguments += "-NoExit"
    }
    $arguments += @("-EncodedCommand", $encoded)
    Start-Process -Verb RunAs -FilePath "powershell.exe" -ArgumentList $arguments -WorkingDirectory $WorkingDirectory
}
