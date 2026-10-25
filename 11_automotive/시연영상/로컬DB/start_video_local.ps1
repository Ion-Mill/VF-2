# 영상용(video) 서버 묶음을 로컬 Docker DB(mom-video-db, localhost:5433)에 연결해 켠다. 공용 Supabase는 건드리지 않는다.
# 코드·설정 파일은 고치지 않는다 (backend\.env.local-video 만 읽는다). 끄기: stop_video_local.ps1
$ErrorActionPreference = 'Stop'
$Auto = (Resolve-Path "$PSScriptRoot\..\..").Path      # 11_automotive
$Run = "$PSScriptRoot\run"
New-Item -ItemType Directory -Force -Path $Run | Out-Null
$pids = New-Object System.Collections.ArrayList

function Start-P([string]$Name, [string]$Exe, [string[]]$A, [string]$Cwd, [hashtable]$E) {
    $saved = @{}
    foreach ($k in $E.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process'); [Environment]::SetEnvironmentVariable($k, $E[$k], 'Process') }
    try { $p = Start-Process -FilePath $Exe -ArgumentList $A -WorkingDirectory $Cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput "$Run\$Name.log" -RedirectStandardError "$Run\$Name.err.log" }
    finally { foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') } }
    [void]$pids.Add([pscustomobject]@{ Name = $Name; Pid = $p.Id })
    $pids | ConvertTo-Json | Set-Content "$Run\pids.json" -Encoding UTF8
    return $p
}
function Wait-Url([string]$Url, [int]$Sec = 90) {
    $t = (Get-Date).AddSeconds($Sec)
    while ((Get-Date) -lt $t) { try { Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4 | Out-Null; return $true } catch { Start-Sleep -Milliseconds 800 } }
    return $false
}
$u = @{ PYTHONUTF8 = '1'; PYTHONUNBUFFERED = '1' }
$BackendUrl = 'http://127.0.0.1:8000'

# 1. 백엔드 (로컬 DB)
$e = $u.Clone(); $e['MOM_ASSISTANT_URL'] = 'http://127.0.0.1:8100'
Start-P 'backend' "$Auto\backend\.venv\Scripts\python.exe" @('-m', 'uvicorn', 'app.main:app', '--env-file', '.env.local-video', '--port', '8000') "$Auto\backend" $e | Out-Null
if (-not (Wait-Url "$BackendUrl/api/health")) { Write-Host '백엔드 안 켜짐'; Get-Content "$Run\backend.err.log" -Tail 12; exit 1 }
Write-Host '백엔드 OK'
# 2. 비서
$e = $u.Clone(); $e['MOM_BACKEND_URL'] = $BackendUrl
Start-P 'assistant' "$Auto\assistant\.venv\Scripts\python.exe" @('-m', 'uvicorn', 'backend.chat_service:app', '--host', '127.0.0.1', '--port', '8100') "$Auto\assistant" $e | Out-Null
Start-Sleep 6
Write-Host '비서 시작함'
# 3. 시연 서버 (영상용 프로필, DB 중계는 .env.local-video 의 MOM_SIM_SYNC·MOM_INGEST_KEY 를 읽어 켜짐)
$e = $u.Clone(); $e['MOM_PROFILE'] = 'video'; $e['MOM_LLM_COMPOSE'] = '1'; $e['MOM_BACKEND_URL'] = $BackendUrl; $e['MOM_ENV_FILE'] = '.env.local-video'
Start-P 'sim_server' "$Auto\생성기\.venv\Scripts\python.exe" @('tools\sim_server.py') "$Auto\frontend" $e | Out-Null
if (-not (Wait-Url 'http://127.0.0.1:8765/api/health')) { Write-Host '시연 서버 안 켜짐'; Get-Content "$Run\sim_server.err.log" -Tail 12; exit 1 }
Write-Host '시연 서버 OK'
# 4. 화면 (백엔드 길, 새 비서 채팅)
$e = @{ NEXT_PUBLIC_MOM_API = $BackendUrl }
Start-P 'screen' (Get-Command node).Source @("$Auto\frontend\node_modules\next\dist\bin\next", 'dev', '-p', '3000') "$Auto\frontend" $e | Out-Null
if (-not (Wait-Url 'http://localhost:3000' 150)) { Write-Host '화면 안 켜짐'; Get-Content "$Run\screen.err.log" -Tail 12; exit 1 }
Write-Host '화면 OK'
