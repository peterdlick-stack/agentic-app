$ErrorActionPreference='Stop'
$e='F:/context-recommend-repair-20261004-180749'
$start=(Get-Date).ToUniversalTime().ToString('o')
$track=Get-ChildItem -LiteralPath 'F:/context-player-cache-20261004/library' -Filter '*.wav' | Where-Object Length -gt 100000 | Select-Object -First 1
& powershell.exe -NoProfile -File "$e/play.ps1" -AudioPath $track.FullName -Seconds 2 -Volume 0
$playExit=$LASTEXITCODE
$args=@('-NoProfile','-File',('"'+$e+'/play.ps1"'),'-AudioPath',('"'+$track.FullName+'"'),'-Seconds','20','-Volume','0')
$proc=Start-Process -FilePath 'powershell.exe' -ArgumentList $args -PassThru -WindowStyle Hidden -RedirectStandardOutput "$e/tmp/play-controller.log" -RedirectStandardError "$e/tmp/play-controller.err"
$controllerHandle=$proc.Handle
Start-Sleep -Seconds 2
$playing=Get-Content -Raw -LiteralPath "$e/playback-process.json" | ConvertFrom-Json
$before=Get-Process -Id $playing.pid -ErrorAction SilentlyContinue
$matched=$before -and $before.StartTime.ToUniversalTime().Ticks -eq $playing.startTicks -and $before.Path -eq $playing.exe
& "$e/STOP.cmd"
$stopExit=$LASTEXITCODE
$proc.WaitForExit()
$after=Get-Process -Id $playing.pid -ErrorAction SilentlyContinue
$stopped=-not ($after -and $after.StartTime.ToUniversalTime().Ticks -eq $playing.startTicks)
'q' | & "$e/START.cmd"
$startExit=$LASTEXITCODE
& "$e/STOP.cmd"
$idleExit=$LASTEXITCODE
$hashes=@{}
foreach($name in @('START.cmd','STOP.cmd','RETEST.cmd','play.ps1','stop.ps1')){$hashes[$name]=(Get-FileHash -LiteralPath "$e/$name" -Algorithm SHA256).Hash.ToLower()}
$result=@{start_utc=$start;end_utc=(Get-Date).ToUniversalTime().ToString('o');play_command=@('powershell.exe','-NoProfile','-File',"$e/play.ps1",'-AudioPath',$track.FullName,'-Seconds','2','-Volume','0');play_exit=$playExit;stop_exit=$stopExit;controller_exit=$proc.ExitCode;start_exit=$startExit;idle_stop_exit=$idleExit;matched_before_stop=[bool]$matched;exact_pid_stopped=$stopped;audibility='NOT_RUN_MUTED';hashes=$hashes;process=$playing}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$e/entrypoints.json" -Encoding UTF8
if($playExit -ne 0 -or $stopExit -ne 0 -or $proc.ExitCode -ne 0 -or $startExit -ne 0 -or $idleExit -ne 0 -or -not $matched -or -not $stopped){exit 1}
'Native entrypoints PASS'
