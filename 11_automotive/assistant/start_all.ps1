<#
.SYNOPSIS
  백엔드(기본 8020)와 AI 비서 서비스(기본 8100)를 한 번에 켠다. 끄는 것은 stop_all.ps1.

.DESCRIPTION
  실행_안내.md 5절의 5-2·5-3을 한 번에 하는 스크립트다. 코드를 합치지 않고 켜는 일만 묶는다.
  - 켜기 전에 설정을 읽기만 해서 점검한다 (가상환경, 설정 파일, 두 파일의 MOM_ASSISTANT_KEY 일치, 공용 DB 쓰기 방지 설정).
  - 이미 그 포트에 켜진 서버는 끄지도 덮어쓰지도 않는다. 건강한 서버면 그대로 쓰고, 다른 프로그램이면 멈춘다.
  - 이 스크립트가 켠 것만 .run\pids.json 에 적어 두고 stop_all.ps1 이 그것만 끈다. 로그는 .run\ 에 남는다.
  - 포트를 바꾸면 두 서비스가 서로를 찾는 주소(MOM_BACKEND_URL, MOM_ASSISTANT_URL)를 켜는 프로세스에만 맞춰 준다. 설정 파일은 고치지 않는다.
  - 비밀번호·키는 화면에 찍지 않는다.

.PARAMETER BackendPort    백엔드 포트 (기본 8020)
.PARAMETER AssistantPort  비서 서비스 포트 (기본 8100)
.PARAMETER Screen         시연 서버(8765)와 화면(기본 3000)도 켠다. 이미 켜져 있으면 건드리지 않는다.
.PARAMETER ScreenPort     화면 포트 (기본 3000). 3000이 아니면 백엔드 MOM_CORS_ORIGINS 에 그 주소가 있어야 한다.
.PARAMETER NewChat        -Screen 과 같이 쓴다. 이브 채팅 탭을 새 비서에 잇는다 (켜는 화면 프로세스에만 NEXT_PUBLIC_MOM_API 를 준다. frontend\.env.local 은 만들지 않는다).
.PARAMETER LlmCompose     -Screen 과 같이 쓴다. 시연 서버를 켤 때 MOM_LLM_COMPOSE=1 을 그 프로세스에만 준다 — 교대·일일 보고서 문장, 작업지시서 제목·증상, 지침카드 "먼저 할 일" 풀이를 비서(외부 Claude)가 다듬는다.
                  이 옵션 없이 켜면 시연 서버의 문장 다듬기는 꺼진다(기본). 이미 켜져 있는 시연 서버에는 적용되지 않는다 (환경변수는 켤 때 읽는다) — 끄고 다시 켠다.
.PARAMETER CheckDb        켜기 전에 공용 DB 접속 점검(읽기만)을 먼저 한다.
.PARAMETER WaitSeconds    준비될 때까지 기다리는 최대 시간 (기본 60초)
.PARAMETER DryRun         아무것도 켜지 않고 무엇을 할지만 보여 준다 (설정 점검은 한다).

.EXAMPLE
  .\11_automotive\assistant\start_all.ps1
.EXAMPLE
  .\11_automotive\assistant\start_all.ps1 -Screen -NewChat
.EXAMPLE
  .\11_automotive\assistant\start_all.ps1 -Screen -LlmCompose
.EXAMPLE
  .\11_automotive\assistant\start_all.ps1 -BackendPort 8021 -AssistantPort 8101 -DryRun
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8020,
    [int]$AssistantPort = 8100,
    [switch]$Screen,
    [int]$ScreenPort = 3000,
    [switch]$NewChat,
    [switch]$LlmCompose,
    [switch]$CheckDb,
    [int]$WaitSeconds = 60,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$AssistantDir = $PSScriptRoot
$Auto = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Auto 'backend'
$FrontendDir = Join-Path $Auto 'frontend'
$BackendPy = Join-Path $BackendDir '.venv\Scripts\python.exe'
$AssistantPy = Join-Path $AssistantDir '.venv\Scripts\python.exe'
$SimPy = Join-Path $Auto '생성기\.venv\Scripts\python.exe'
$BackendEnv = Join-Path $BackendDir '.env.supabase'
$AssistantEnv = Join-Path $AssistantDir '.env'
$RunDir = Join-Path $AssistantDir '.run'
$PidFile = Join-Path $RunDir 'pids.json'
$SimPort = 8765          # frontend\tools\sim_server.py 안에 박혀 있다 (바꿀 수 없다)

$Started = New-Object System.Collections.ArrayList     # 이번 실행에서 켠 것 (실패하면 되돌린다)

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }

function Hide-Secrets([string]$Text) {
    # 접속 주소 안의 비밀번호를 가린다 (로그를 화면에 보일 때)
    return [regex]::Replace($Text, '://([^:/@\s]+):([^@\s]+)@', '://$1:***@')
}

function Get-EnvValue([string]$File, [string]$Name) {
    if (-not (Test-Path -LiteralPath $File)) { return $null }
    foreach ($line in Get-Content -LiteralPath $File -Encoding UTF8) {
        if ($line -match ('^\s*' + [regex]::Escape($Name) + '\s*=\s*(.*)$')) { return $Matches[1].Trim().Trim('"').Trim("'") }
    }
    return $null
}

function Read-PidEntries {
    # Windows PowerShell 5.1 의 ConvertFrom-Json 은 JSON 배열을 풀어 주지 않고 통째로 하나로 내놓는다 → ForEach-Object 로 풀어서 5.1·7 모두 같게
    if (-not (Test-Path -LiteralPath $PidFile)) { return @() }
    return @(Get-Content -LiteralPath $PidFile -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object { $_ })
}

function Save-Pids {
    if ($Started.Count -eq 0 -and -not (Test-Path -LiteralPath $PidFile)) { return }
    $all = Read-PidEntries
    $merged = @($all | Where-Object { $e = $_; -not ($Started | Where-Object { $_.Name -eq $e.Name }) }) + @($Started)
    if ($merged.Count -eq 0) { Remove-Item -LiteralPath $PidFile -Force; return }
    ConvertTo-Json -InputObject $merged -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8
}

function Stop-Tree([int]$ProcessId) {
    # 프로세스와 그 자식을 함께 끈다 (Windows 의 venv python 은 실제 서버를 자식으로 띄운다). 외부 프로그램의 오류 출력이 중단으로 번지지 않게 한다.
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & taskkill.exe /PID $ProcessId /T /F 2>&1 | Out-Null } finally { $ErrorActionPreference = $old }
}

function Fail([string]$Text) {
    Say "[중단] $Text" Red
    if ($Started.Count -gt 0) {
        Say '이번에 켠 것을 되돌린다...' Yellow
        $names = @($Started | ForEach-Object { $_.Name })
        foreach ($e in $Started) { Stop-Tree $e.Pid }
        $Started.Clear()
        if (Test-Path -LiteralPath $PidFile) {
            $left = @(Read-PidEntries | Where-Object { $names -notcontains $_.Name })
            if ($left.Count -gt 0) { ConvertTo-Json -InputObject $left -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8 } else { Remove-Item -LiteralPath $PidFile -Force }
        }
    }
    exit 1
}

function Get-Listener([int]$Port) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $c) { return $null }
    $p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $c.OwningProcess) -ErrorAction SilentlyContinue
    $full = ''
    if ($p -and $p.CommandLine) { $full = $p.CommandLine }
    $cmd = $full
    if ($cmd.Length -gt 110) { $cmd = $cmd.Substring(0, 110) + '...' }
    return [pscustomobject]@{ Pid = $c.OwningProcess; Cmd = $cmd; FullCmd = $full }
}

function Get-PlanLabel([string]$Plan) {
    if ($Plan -eq 'reuse') { return '이미 켜져 있어 그대로 씀' }
    if ($Plan -eq 'start') { if ($DryRun) { return '켤 예정' } else { return '새로 켬' } }
    return '건너뜀'
}

function Test-Url([string]$Url, [hashtable]$Headers = @{}) {
    try {
        $r = Invoke-WebRequest -Uri $Url -Headers $Headers -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

# ---------------------------------------------------------------- 1. 설정 점검 (읽기만)
Say '== 1. 설정 점검 (읽기만) ==' Cyan
foreach ($f in @(
        @{ Path = $BackendPy; Hint = '백엔드 가상환경이 없다 — 실행_안내.md 4-1' },
        @{ Path = $AssistantPy; Hint = '비서 가상환경이 없다 — 실행_안내.md 4-1' },
        @{ Path = $BackendEnv; Hint = 'backend\.env.supabase 가 없다 — 실행_안내.md 4-2' },
        @{ Path = $AssistantEnv; Hint = 'assistant\.env 가 없다 — 실행_안내.md 4-2' })) {
    if (-not (Test-Path -LiteralPath $f.Path)) { Fail ($f.Hint + "  ($($f.Path))") }
}
if ($Screen) {
    if (-not (Test-Path -LiteralPath $SimPy)) { Fail "시연 서버용 가상환경이 없다: $SimPy  (생성기 폴더의 .venv)" }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules\next\dist\bin\next'))) { Fail 'frontend\node_modules 가 없다 — frontend 에서 npm install 을 먼저 한다' }
    $NodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $NodeCmd) { Fail 'node 를 찾을 수 없다 (화면에 필요)' }
}
if ($NewChat -and -not $Screen) { Say '[알림] -NewChat 은 -Screen 과 같이 쓸 때만 뜻이 있다. 무시한다.' Yellow }
if ($LlmCompose -and -not $Screen) { Say '[알림] -LlmCompose 는 -Screen 과 같이 쓸 때만 뜻이 있다 (시연 서버가 읽는 스위치다). 무시한다.' Yellow }

$keyB = Get-EnvValue $BackendEnv 'MOM_ASSISTANT_KEY'
$keyA = Get-EnvValue $AssistantEnv 'MOM_ASSISTANT_KEY'
if ([string]::IsNullOrEmpty($keyB) -or [string]::IsNullOrEmpty($keyA)) { Fail '두 설정 파일 모두에 MOM_ASSISTANT_KEY 가 있어야 한다 (비어 있으면 비서가 모든 요청을 401로 거절한다)' }
if ($keyB -cne $keyA) { Fail 'backend\.env.supabase 와 assistant\.env 의 MOM_ASSISTANT_KEY 가 서로 다르다 (같은 값이어야 한다. 값은 화면에 찍지 않는다)' }
foreach ($name in 'MOM_DATABASE_URL', 'MOM_READONLY_DATABASE_URL') {
    $v = Get-EnvValue $BackendEnv $name
    if ([string]::IsNullOrEmpty($v)) { Fail "backend\.env.supabase 에 $name 가 없다" }
    if ($v.Contains('<') -or $v.Contains('>')) { Fail "$name 의 비밀번호 자리가 아직 <...> 그대로다 (DB 담당에게 받은 값으로 채운다)" }
}
# 공용 DB를 지키는 설정: MOM_RUN_WORKERS 기본값은 true(스케줄러·파일 감시가 돈다)라 줄이 없어도 위험하다
# 2026-10-24: 화면 → 백엔드가 기본이 되면서, 10/1 중계를 받는 진행자 서버(MOM_SIM_SYNC=true)는 스케줄러도 돌린다 (교대 보고서 초안·시간 규칙 알림 — 같은 DB에 여러 대가 떠도 DB 잠금으로 한 번만 돈다)
$workers = Get-EnvValue $BackendEnv 'MOM_RUN_WORKERS'
$sync = Get-EnvValue $BackendEnv 'MOM_SIM_SYNC'
$syncOn = ($null -ne $sync) -and (@('true', '1', 'yes', 'on') -contains $sync.ToLower())
$workersOff = ($null -ne $workers) -and (@('false', '0', 'no', 'off') -contains $workers.ToLower())
if (-not $syncOn -and -not $workersOff) { Fail 'backend\.env.supabase 에 MOM_RUN_WORKERS=false 가 있어야 한다 (줄이 없으면 기본값이 true라 공용 DB에서 스케줄러가 돈다). 진행자 서버(MOM_SIM_SYNC=true)만 true 가능' }
if ($syncOn) { Say "[알림] MOM_SIM_SYNC=true — 이 PC가 시연 진행자(10/1 중계를 공용 DB에 씀). 시연 서버를 켜면 공용 DB가 10/1 08:00 기준점으로 되돌아간다 (채팅 기록 포함). 스케줄러: $(if ($workersOff) { '꺼짐 — 교대 끝 보고서 초안이 안 생긴다. MOM_RUN_WORKERS=true 권장' } else { '켜짐' })" Yellow }
$demo = Get-EnvValue $BackendEnv 'MOM_DEMO_MODE'
if ($null -ne $demo -and @('true', '1', 'yes', 'on') -contains $demo.ToLower()) { Fail 'backend\.env.supabase 에 MOM_DEMO_MODE=true 다. 공용 DB에서는 false 여야 한다 (시연 되돌리기 같은 쓰기 API가 열린다)' }
if ($Screen) {
    $cors = Get-EnvValue $BackendEnv 'MOM_CORS_ORIGINS'
    if ($NewChat -and $cors -and -not $cors.Contains(":$ScreenPort")) { Say "[주의] MOM_CORS_ORIGINS 에 화면 포트 $ScreenPort 가 없다. 브라우저가 백엔드를 부를 때 막힌다 — backend\.env.supabase 에 http://localhost:$ScreenPort 를 더한다." Yellow }
}
Say '설정 파일·가상환경·키 일치·공용 DB 쓰기 방지 설정 OK (값은 찍지 않는다)' Green

# ---------------------------------------------------------------- 2. 무엇을 할지 정하기
Say '== 2. 포트 확인 ==' Cyan
$BackendUrl = "http://127.0.0.1:$BackendPort"
$AssistantUrl = "http://127.0.0.1:$AssistantPort"
$ServiceHeaders = @{ 'X-Service-Key' = $keyA }

function Resolve-Port([string]$Label, [int]$Port, [scriptblock]$IsOurs) {
    $l = Get-Listener $Port
    if (-not $l) { return 'start' }
    if (& $IsOurs $l) {
        Say "[$Label] 포트 $Port 에 이미 켜져 있다 (pid $($l.Pid)). 건드리지 않고 그대로 쓴다 — 그 서버의 코드가 최신인지는 확인하지 않는다." Yellow
        return 'reuse'
    }
    Fail "[$Label] 포트 $Port 를 다른 프로그램이 쓰고 있다 (pid $($l.Pid): $($l.Cmd)). 그 프로그램은 끄지 않는다. 다른 포트를 쓰거나(예: -BackendPort, -AssistantPort) 직접 끈다."
}

# "우리 서버인지"는 건강 확인만으로 알 수 없다 (옛 모의 서버 8000 도 /api/health 에 200으로 답한다). 명령줄에 서버 이름이 있는지도 함께 본다.
$planBackend = Resolve-Port '백엔드' $BackendPort { param($l) ($l.FullCmd -like '*app.main:app*') -and (Test-Url "$BackendUrl/api/health") }
$planAssistant = Resolve-Port '비서' $AssistantPort { param($l) ($l.FullCmd -like '*backend.chat_service:app*') -and (Test-Url "$AssistantUrl/health" $ServiceHeaders) }
$planSim = 'skip'; $planScreen = 'skip'
if ($Screen) {
    $planSim = Resolve-Port '시연 서버' $SimPort { param($l) $l.FullCmd -like '*sim_server*' }
    $planScreen = Resolve-Port '화면' $ScreenPort { param($l) $l.FullCmd -like '*next*' }
    if ($NewChat -and $planScreen -eq 'reuse') { Say '[주의] 이미 켜져 있는 화면에는 -NewChat 이 적용되지 않는다 (환경변수는 화면을 켤 때 읽는다). 화면을 끄고 다시 켜거나 frontend\.env.local 을 쓴다.' Yellow }
}
# 시연 서버의 문장 다듬기(MOM_LLM_COMPOSE) 상태 — 요약에 보인다: on | off | unknown (-LlmCompose 를 쓴 때만)
$simCompose = $null
if ($Screen -and $LlmCompose) {
    if ($planSim -eq 'start') { $simCompose = 'on' }
    else {
        # 이미 켜져 있는 시연 서버는 환경변수를 다시 읽지 않는다 — 지금 켜져 있는지 읽어서 알린다 (GET 만)
        try {
            $h = Invoke-WebRequest -Uri "http://127.0.0.1:$SimPort/api/health" -UseBasicParsing -TimeoutSec 3
            $simCompose = $(if (($h.Content | ConvertFrom-Json).llm_compose.enabled) { 'on' } else { 'off' })
        } catch { $simCompose = 'unknown' }
        if ($simCompose -ne 'on') { Say '[주의] 이미 켜져 있는 시연 서버에는 -LlmCompose 가 적용되지 않는다 (환경변수는 켤 때 읽는다). 시연 서버만 끄고 다시 켠다 (실행_안내.md 맨 앞 결론 ④).' Yellow }
    }
}

# ---------------------------------------------------------------- 3. 켜기
function Start-Proc([string]$Name, [string]$Exe, [string[]]$ArgList, [string]$Cwd, [hashtable]$ExtraEnv, [string]$Marker, [int]$Port) {
    $log = Join-Path $RunDir "$Name.log"
    $err = Join-Path $RunDir "$Name.err.log"
    if ($DryRun) {
        Say "  [예행] $Name : $Exe $($ArgList -join ' ')" DarkGray
        Say "         폴더 $Cwd | 이 프로세스에만 주는 환경변수: $($ExtraEnv.Keys -join ', ') | 로그 $log" DarkGray
        return $null
    }
    New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
    $quoted = @($ArgList | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } })     # 경로에 공백이 있어도 한 덩어리로
    $saved = @{}
    foreach ($k in $ExtraEnv.Keys) {
        $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process')
        [Environment]::SetEnvironmentVariable($k, $ExtraEnv[$k], 'Process')
    }
    try {
        $p = Start-Process -FilePath $Exe -ArgumentList $quoted -WorkingDirectory $Cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    } finally {
        foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') }
    }
    [void]$Started.Add([pscustomobject]@{ Name = $Name; Pid = $p.Id; Port = $Port; Marker = $Marker; StartTime = $p.StartTime.ToString('o'); Log = $log })
    Save-Pids
    return $p
}

function Wait-Ready([string]$Label, $Proc, [scriptblock]$Ready, [string]$ErrLog) {
    if ($DryRun -or $null -eq $Proc) { return }
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Proc.HasExited) {
            Say "--- $Label 로그 끝부분 (비밀번호는 가림) ---" DarkGray
            if (Test-Path -LiteralPath $ErrLog) { Get-Content -LiteralPath $ErrLog -Tail 12 -Encoding UTF8 | ForEach-Object { Say (Hide-Secrets $_) DarkGray } }
            Fail "$Label 가 켜지다 꺼졌다 (종료 코드 $($Proc.ExitCode)). 로그: $ErrLog"
        }
        if (& $Ready) { return }
        Start-Sleep -Milliseconds 700
    }
    Fail "$Label 가 $WaitSeconds 초 안에 준비되지 않았다. 로그: $ErrLog"
}

if ($CheckDb -and -not $DryRun) {
    Say '== 3-0. 공용 DB 접속 점검 (읽기만) ==' Cyan
    Push-Location $BackendDir
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'      # 외부 프로그램의 오류 출력이 중단으로 번지지 않게
    try {
        & $BackendPy 'tools\check_connection.py' '--env-file' '.env.supabase' 2>&1 | ForEach-Object { Say (Hide-Secrets ([string]$_)) }
        $dbExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old; Pop-Location }
    if ($dbExit -ne 0) { Fail 'DB 접속 점검이 실패했다. 위 내용을 확인한다 (DB 담당에게 받은 값, 인터넷).' }
}

Say '== 3. 켜기 ==' Cyan
$utf8 = @{ PYTHONUTF8 = '1'; PYTHONUNBUFFERED = '1' }

if ($planBackend -eq 'start') {
    $envB = $utf8.Clone(); $envB['MOM_ASSISTANT_URL'] = $AssistantUrl
    $pB = Start-Proc 'backend' $BackendPy @('-m', 'uvicorn', 'app.main:app', '--env-file', '.env.supabase', '--port', "$BackendPort") $BackendDir $envB 'app.main:app' $BackendPort
    Wait-Ready '백엔드' $pB { Test-Url "$BackendUrl/api/health" } (Join-Path $RunDir 'backend.err.log')
    if (-not $DryRun) { Say "백엔드 준비 OK  $BackendUrl" Green }
}
if ($planAssistant -eq 'start') {
    $envA = $utf8.Clone(); $envA['MOM_BACKEND_URL'] = $BackendUrl
    $pA = Start-Proc 'assistant' $AssistantPy @('-m', 'uvicorn', 'backend.chat_service:app', '--host', '127.0.0.1', '--port', "$AssistantPort") $AssistantDir $envA 'backend.chat_service:app' $AssistantPort
    Wait-Ready '비서' $pA { Test-Url "$AssistantUrl/health" $ServiceHeaders } (Join-Path $RunDir 'assistant.err.log')
    if (-not $DryRun) { Say "비서 준비 OK  $AssistantUrl" Green }
}
if ($planSim -eq 'start') {
    $envS = $utf8.Clone()
    if ($LlmCompose) { $envS['MOM_LLM_COMPOSE'] = '1' }       # 시연 서버 프로세스에만 준다 (다른 서버·이 창에는 남지 않는다)
    $envS['MOM_BACKEND_URL'] = $BackendUrl                     # DB 중계가 보낼 백엔드 (backend\.env.supabase 에 MOM_SIM_SYNC=true 일 때만 켜짐, 2026-10-24)
    $pS = Start-Proc 'sim_server' $SimPy @('tools\sim_server.py') $FrontendDir $envS 'sim_server' $SimPort
    Wait-Ready '시연 서버' $pS { [bool](Get-NetTCPConnection -State Listen -LocalPort $SimPort -ErrorAction SilentlyContinue) } (Join-Path $RunDir 'sim_server.err.log')
    if (-not $DryRun) { Say "시연 서버 준비 OK  http://127.0.0.1:$SimPort" Green }
}
if ($planScreen -eq 'start') {
    $envW = @{ MOM_BACKEND_URL = $BackendUrl }                 # 화면 서버가 /api 를 이 백엔드로 넘긴다 (화면 → 백엔드가 기본, 2026-10-24 — next.config.mjs)
    if ($NewChat) { $envW['NEXT_PUBLIC_MOM_API'] = $BackendUrl }
    $nextBin = Join-Path $FrontendDir 'node_modules\next\dist\bin\next'
    $pW = Start-Proc 'screen' $NodeCmd.Source @($nextBin, 'dev', '-p', "$ScreenPort") $FrontendDir $envW 'next' $ScreenPort
    Wait-Ready '화면' $pW { [bool](Get-NetTCPConnection -State Listen -LocalPort $ScreenPort -ErrorAction SilentlyContinue) } (Join-Path $RunDir 'screen.err.log')
    if (-not $DryRun) { Say "화면 준비 OK  http://localhost:$ScreenPort  (처음 열 때 컴파일로 몇 초 걸린다)" Green }
}

# ---------------------------------------------------------------- 4. 요약
Say ''
Say ($(if ($DryRun) { '== 예행 연습 끝 (아무것도 켜지 않았다) ==' } else { '== 켜졌다 ==' })) Cyan
Say "  백엔드   $BackendUrl/docs   [$(Get-PlanLabel $planBackend)]"
Say "  비서     $AssistantUrl   [$(Get-PlanLabel $planAssistant)]  (밖에 열지 않는다. 확인할 때는 X-Service-Key 헤더가 필요하다)"
if ($Screen) {
    Say "  시연서버 http://127.0.0.1:$SimPort   [$(Get-PlanLabel $planSim)]"
    if ($LlmCompose) {
        if ($simCompose -eq 'on') {
            $state = $(if ($planSim -ne 'start') { '이미 켜져 있음' } elseif ($DryRun) { '켤 예정' } else { '켜짐' })
            Say "  문장 다듬기 $state (-LlmCompose) — 보고서 둘·작업지시서·지침카드 문장이 외부 Claude로 간다 (가상 데이터 문장만, 한 스위치로 네 곳이 함께)" Yellow
        }
        else { Say "  문장 다듬기 [적용 안 됨] — 이미 켜져 있는 시연 서버에는 닿지 않는다 (지금 상태: $simCompose)" Yellow }
    } elseif ($planSim -eq 'start') { Say '  문장 다듬기 꺼짐 (-LlmCompose 를 쓰지 않았다)' }
    Say "  화면     http://localhost:$ScreenPort   [$(Get-PlanLabel $planScreen)]  채팅 탭: $(if ($NewChat -and $planScreen -eq 'start') { '새 비서(외부 LLM)에 잇는다' } else { '스위치 상태 그대로 (frontend\.env.local 에 따름)' })"
}
$prov = Get-EnvValue $AssistantEnv 'ASSISTANT_PROVIDER'; $ext = Get-EnvValue $AssistantEnv 'EXTERNAL_LLM_APP'; $llm = Get-EnvValue $AssistantEnv 'LLM_ENABLED'
if ($prov -eq 'claude' -and $ext -eq '1' -and $llm -eq '1') { Say '  외부 Claude: 켜짐 — 질문과 사내 문서 조각이 외부로 나간다 (지금은 가상 데이터만 쓴다)' Yellow } else { Say '  외부 Claude: 꺼짐 (assistant\.env 기준) — 규칙·기본 문장으로만 답한다' }
if (-not $DryRun) {
    Say "  로그    $RunDir"
    Say '  끄기    .\11_automotive\assistant\stop_all.ps1   (이 스크립트가 켠 것만 끈다)'
    Say '  주의    공용 DB다. 질문하면 chat_log·access_log 에 기록이 남는다 (실행_안내.md 9절)'
}
exit 0
