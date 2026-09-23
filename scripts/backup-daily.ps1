# Orbit's nightly backup, for Windows Task Scheduler.
#
# Register it (as an administrator), then check it the next morning:
#   schtasks /Create /TN "Orbit backup" /TR "powershell -ExecutionPolicy Bypass -File <full path to this file>" /SC DAILY /ST 02:00 /RL HIGHEST /F
#
# See docs\backups.md. Set BackupDir to a folder that is synced or copied off
# this machine: an archive that only exists here does not survive losing here.

# -BackupDir is only for trying the script out; the scheduled task uses the default.
param([string]$BackupDir = 'D:\orbit-backups')

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
$LogFile = Join-Path $BackupDir 'backup.log'

function Write-Log($message) {
    $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message
    Write-Output $line
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

try {
    if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }

    Set-Location $ProjectDir
    Write-Log "starting backup into $BackupDir"

    # uv writes progress to stderr; keep both streams in the log so a failure
    # leaves a reason behind rather than a bare exit code.
    $output = & uv run python -m app.tools.backup --out-dir $BackupDir 2>&1
    $code = $LASTEXITCODE

    foreach ($line in $output) { Write-Log "  $line" }

    if ($code -ne 0) {
        Write-Log "FAILED with exit code $code"
        exit $code
    }
    Write-Log 'done'
    exit 0
}
catch {
    # Task Scheduler only sees the exit code, so the reason has to reach the log.
    try { Write-Log "FAILED: $($_.Exception.Message)" } catch { }
    exit 1
}
