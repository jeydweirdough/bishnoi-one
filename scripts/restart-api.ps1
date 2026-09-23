<#
.SYNOPSIS
  Restart the Orbit API cleanly, leaving no process behind on port 8000.

.DESCRIPTION
  uvicorn's reloader is two processes: a parent that watches files and a worker
  child that actually serves. Killing the parent alone leaves the worker holding
  the port and serving the code it loaded at startup — so edits appear to do
  nothing, and the server looks perfectly healthy while answering from a copy of
  the code that no longer exists on disk.

  The worker is easy to miss: its command line is the multiprocessing spawn
  string, so it does not contain "main.py". This kills both, waits for the port
  to actually go quiet, starts one server, and then proves the new one is live.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\restart-api.ps1
#>
[CmdletBinding()]
param(
    [int]    $Port = 8000,
    [string] $Python = "env\Scripts\python.exe",
    [string] $Entry = "main.py",
    [string] $LogFile = ".data\api.log",
    [int]    $TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-Api {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 -UseBasicParsing
        return $true
    } catch {
        return $false
    }
}

# 1. Stop both halves. The worker matches on --multiprocessing-fork, which is
#    the part a "kill anything running main.py" misses.
$ours = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -and ($_.CommandLine -like "*$Entry*" -or $_.CommandLine -like "*--multiprocessing-fork*")
}
foreach ($p in $ours) {
    Write-Host "stopping $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# 2. Wait for the port to go quiet. A listener that answers after the kill is an
#    orphan we failed to find, and starting a second server on top of it would
#    put us straight back where we were.
$deadline = (Get-Date).AddSeconds(15)
while ((Test-Api) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
if (Test-Api) {
    throw "Something is still serving port $Port. Find it with: Get-NetTCPConnection -LocalPort $Port -State Listen"
}

# 3. Start one, detached, with its output on disk.
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
Start-Process -FilePath $Python -ArgumentList $Entry `
    -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
    -WindowStyle Hidden | Out-Null

# 4. Prove it is up before saying so.
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while (-not (Test-Api) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
if (-not (Test-Api)) {
    Write-Host "--- $LogFile.err ---"
    if (Test-Path "$LogFile.err") { Get-Content "$LogFile.err" -Tail 30 }
    throw "The API did not come up within $TimeoutSeconds seconds."
}

Write-Host "API is up on http://127.0.0.1:$Port  (log: $LogFile)"
