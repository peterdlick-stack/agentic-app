$ErrorActionPreference='Stop'
$r='F:/context-recommend-repair-20261004-180749'
$record="$r/playback-process.json"
if(Test-Path -LiteralPath $record){
 $x=Get-Content -Raw -LiteralPath $record | ConvertFrom-Json
 $p=Get-Process -Id $x.pid -ErrorAction SilentlyContinue
 if($p -and $p.StartTime.ToUniversalTime().Ticks -eq $x.startTicks -and $p.Path -eq $x.exe){ $x | Add-Member -NotePropertyName stopRequested -NotePropertyValue $true -Force; $x | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath $record; Stop-Process -Id $p.Id; Write-Output 'Stopped this candidate playback' } else {Write-Output 'No matching candidate playback'}
}

