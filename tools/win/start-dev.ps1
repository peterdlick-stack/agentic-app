# start-dev.ps1 - start the Windows-native OctoSense desktop (0.1.0-rc.5) against the
# local App Hub mirror made by tools/win/republish.sh. All OctoSense state for this
# instance (app data, AI provider settings, logs) stays under -Root.
#
# Usage (PowerShell, from the repository root):
#   powershell -ExecutionPolicy Bypass -File tools\win\start-dev.ps1
#   powershell -ExecutionPolicy Bypass -File tools\win\start-dev.ps1 -Root F:\work\context-dj-win
#
# -Root must be the same folder that republish.sh writes to (CDJ_WIN_ROOT there).
# Default: a folder named context-dj-win next to this repository.
# This script stops any running OctoSense first (only one instance can run).
# Kept ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 without a BOM.
param(
  [string]$Root = '',
  [string]$Exe  = "$env:LOCALAPPDATA\OctoSense\octosense.exe",
  [int]$Port    = 8399
)
$ErrorActionPreference = 'Stop'

if (-not $Root) {
  $repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
  $Root = Join-Path (Split-Path $repo -Parent) 'context-dj-win'
}
if (-not (Test-Path $Exe)) {
  throw "OctoSense not found at $Exe. Install the desktop 0.1.0-rc.5 release, or pass -Exe."
}
if (-not (Test-Path "$Root\anchor.pub") -or -not (Test-Path "$Root\mirror\catalog.json")) {
  throw "No local store in $Root. Run tools/win/republish.sh in WSL first (CDJ_WIN_ROOT must point to this folder)."
}

Get-Process octosense,octos-kernel -ErrorAction SilentlyContinue | Stop-Process
New-Item -ItemType Directory -Force "$Root\home","$Root\apps","$Root\logs" | Out-Null

$env:OCTOSENSE_HUB_CATALOG = 'legacy'
$env:OCTOSENSE_HUB         = "$Root\mirror"
$env:OCTOSENSE_HUB_ANCHOR  = (Get-Content "$Root\anchor.pub" -Raw).Trim()
$env:OCTOSENSE_HOME        = "$Root\home"
$env:OCTOSENSE_APP_DATA    = "$Root\apps"
$env:MAKEPAD_REMOTE        = "$Port"

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Start-Process -FilePath $Exe `
  -RedirectStandardOutput "$Root\logs\octosense-$stamp.out.log" `
  -RedirectStandardError  "$Root\logs\octosense-$stamp.err.log"

Write-Host "OctoSense started. Store: $Root\mirror  Data: $Root\apps  Logs: $Root\logs\octosense-$stamp.*.log"
Write-Host "Remote control: http://127.0.0.1:$Port/snap   Quit: curl.exe -s http://127.0.0.1:$Port/quit"
