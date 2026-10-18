<#
.SYNOPSIS
  start_all.ps1 이 켠 서버만 끈다.

.DESCRIPTION
  .run\pids.json 에 적힌 것만 끈다. 직접 켠 서버(다른 터미널, 옛 모의 서버 8000·8010 등)는 건드리지 않는다.
  끄기 전에 그 pid 가 지금도 그때 켠 프로세스인지 확인한다 (명령줄에 켠 서버 이름이 있고 시작 시각이 같아야 한다).
  pid 가 다른 프로그램으로 재사용된 것 같으면 끄지 않고 알린다.

.PARAMETER DryRun  아무것도 끄지 않고 무엇을 끌지만 보여 준다.

.EXAMPLE
  .\11_automotive\assistant\stop_all.ps1
#>
[CmdletBinding()]
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$RunDir = Join-Path $PSScriptRoot '.run'
$PidFile = Join-Path $RunDir 'pids.json'

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }

function Stop-Tree([int]$ProcessId) {
    # 프로세스와 그 자식을 함께 끈다 (Windows 의 venv python 은 실제 서버를 자식으로 띄운다). 비서가 띄운 claude 도 같이 끝난다.
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & taskkill.exe /PID $ProcessId /T /F 2>&1 | Out-Null } finally { $ErrorActionPreference = $old }
}

if (-not (Test-Path -LiteralPath $PidFile)) {
    Say '이 스크립트로 켠 것이 없다 (.run\pids.json 이 없다). 직접 켠 서버는 켠 터미널에서 Ctrl+C 로 끈다.' Yellow
    exit 0
}

# Windows PowerShell 5.1 의 ConvertFrom-Json 은 JSON 배열을 풀어 주지 않고 통째로 하나로 내놓는다 → ForEach-Object 로 풀어서 5.1·7 모두 같게
$entries = @(Get-Content -LiteralPath $PidFile -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object { $_ })
$remaining = @()      # 끄지 못해서 기록에 남겨 둘 것 (다시 시도할 수 있게)
$problems = 0
# 나중에 켠 것부터 끈다 (화면 → 시연 서버 → 비서 → 백엔드)
[array]::Reverse($entries)
foreach ($e in $entries) {
    $label = "$($e.Name) (pid $($e.Pid), 포트 $($e.Port))"
    $proc = Get-Process -Id $e.Pid -ErrorAction SilentlyContinue
    if (-not $proc) {
        Say "[$label] 이미 꺼져 있다." DarkGray
        continue
    }
    $cim = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $e.Pid) -ErrorAction SilentlyContinue
    $cmd = ''
    if ($cim -and $cim.CommandLine) { $cmd = $cim.CommandLine }
    $sameStart = $false
    try { $sameStart = [math]::Abs((([datetime]$e.StartTime).ToUniversalTime() - $proc.StartTime.ToUniversalTime()).TotalSeconds) -lt 5 } catch { $sameStart = $false }
    if (-not $cmd.Contains($e.Marker) -or -not $sameStart) {
        Say "[$label] 그 pid 가 지금은 다른 프로그램 같다 (이름이나 시작 시각이 다르다). 끄지 않는다. 필요하면 직접 확인한다." Yellow
        $problems++
        continue
    }
    if ($DryRun) {
        Say "[$label] 끌 예정 (예행 연습)" DarkGray
        continue
    }
    Stop-Tree $e.Pid
    # 포트가 비워질 때까지 잠깐 기다린다
    $freed = $false
    for ($i = 0; $i -lt 20; $i++) {
        if (-not (Get-NetTCPConnection -State Listen -LocalPort $e.Port -ErrorAction SilentlyContinue)) { $freed = $true; break }
        Start-Sleep -Milliseconds 300
    }
    if ($freed) { Say "[$label] 껐다." Green }
    else {
        Say "[$label] 껐지만 포트 $($e.Port) 가 아직 열려 있다. 다른 프로세스가 쓰고 있을 수 있다 — 직접 확인한다. (기록은 남겨 둔다)" Yellow
        $remaining += $e
        $problems++
    }
}

# 기록 정리: 껐거나, 이미 꺼져 있거나, pid 가 다른 프로그램이 된(더는 우리 것이 아닌) 줄은 지운다. 끄지 못한 줄만 남긴다.
if ($DryRun) {
    Say '(예행 연습이라 .run\pids.json 은 그대로 둔다)' DarkGray
} elseif ($remaining.Count -gt 0) {
    ConvertTo-Json -InputObject $remaining -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8
} elseif (Test-Path -LiteralPath $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}
if ($problems -gt 0) { Say "확인할 것이 $problems 건 있다 (위 노란 줄)." Yellow; exit 1 }
exit 0
