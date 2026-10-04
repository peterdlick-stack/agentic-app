param([Parameter(Mandatory=$true)][string]$AudioPath,[int]$Seconds=20,[int]$Volume=30)
$ErrorActionPreference='Stop'
$r='F:/context-recommend-repair-20261004-180749'
$audioResolved=(Resolve-Path -LiteralPath $AudioPath).Path
if (-not $audioResolved.StartsWith('F:\context-player-cache-20261004\library\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Audio outside library' }
if ($Seconds -lt 1 -or $Seconds -gt 30) { throw 'Duration outside 1..30 seconds' }
$config=Get-Content -LiteralPath 'C:/Users/admin/Downloads/Agentic Apps/work/context-player-real-music-20261004/tools.json' -Raw | ConvertFrom-Json
$env:TEMP="$r/tmp"; $env:TMP="$r/tmp"
$record="$r/playback-process.json"
if (Test-Path -LiteralPath $record) {
 $old=Get-Content -Raw -LiteralPath $record | ConvertFrom-Json
 $existing=Get-Process -Id $old.pid -ErrorAction SilentlyContinue
 if ($existing -and $existing.StartTime.ToUniversalTime().Ticks -eq $old.startTicks) {throw 'This candidate already playing'}
}
$p=Start-Process -FilePath $config.ffplay -ArgumentList @('-nodisp','-autoexit','-loglevel','error','-t',"$Seconds",'-volume',"$Volume",('"'+$audioResolved+'"')) -PassThru -WindowStyle Hidden -RedirectStandardOutput "$r/playback.stdout.log" -RedirectStandardError "$r/playback.stderr.log"
$nativeHandle=$p.Handle # Retain process handle so ExitCode remains available after exit
@{pid=$p.Id;startTicks=$p.StartTime.ToUniversalTime().Ticks;exe=$config.ffplay;stopRequested=$false} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $record
$p.WaitForExit(); $exit=$p.ExitCode
$state=Get-Content -Raw -LiteralPath $record | ConvertFrom-Json
if ($null -eq $exit) {throw "ffplay exit unavailable"}
if ($exit -ne 0 -and -not ($state.pid -eq $p.Id -and $state.stopRequested)) {throw "ffplay exit $exit"}
Write-Output 'Playback process completed. Audibility requires human confirmation.'

