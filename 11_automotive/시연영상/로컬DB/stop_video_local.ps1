# start_video_local.ps1 이 켠 것만 끈다 (DB 컨테이너 mom-video-db 는 그대로 둔다)
$Run = "$PSScriptRoot\run"
if (Test-Path "$Run\pids.json") {
    foreach ($p in (Get-Content "$Run\pids.json" -Raw | ConvertFrom-Json)) {
        if (Get-Process -Id $p.Pid -ErrorAction SilentlyContinue) { taskkill /PID $p.Pid /T /F | Out-Null; "$($p.Name) 껐다" }
    }
    Remove-Item "$Run\pids.json"
}
