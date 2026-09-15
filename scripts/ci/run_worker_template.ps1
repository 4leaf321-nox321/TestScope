Param()
<#
배포된 워커의 기동 스크립트.

    cd <AppPath>
    .\run_worker.ps1

**API 와 별도 프로세스다.** 의미 검색 색인(임베딩)처럼 시간이 걸리는 일을 요청 처리에서
떼어내는 프로세스다. 운영은 이것이 아니라 서비스(`TestScope-Worker`, service.ps1)로 돈다 —
이 스크립트는 문제를 눈으로 볼 때, 또는 -NoService 로 깔았을 때 쓴다.

워커가 없어도 앱은 동작한다 — 다만 작업이 큐에 쌓이기만 하고 처리되지 않는다.
의미 검색 색인이 안 채워지면 워커가 떠 있는지부터 확인한다.

창을 닫으면 멈춘다. 처리 중이던 작업은 다음 기동 때 자동으로 되살아난다(reclaim_stalled).
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path ($scriptDir + '_venvs') 'backend\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Error "가상환경이 없습니다: $venvPython — venv_sync.ps1 -AppPath '$scriptDir' 를 먼저 실행하세요."
    exit 1
}

$backend = Join-Path $scriptDir 'backend'
if (-not (Test-Path (Join-Path $backend 'run_worker.py'))) {
    Write-Error 'backend\run_worker.py 를 찾을 수 없습니다. 패키지가 불완전합니다.'
    exit 1
}

if (-not (Test-Path (Join-Path $backend '.env'))) {
    Write-Error 'backend\.env 가 없습니다. install.ps1 로 만들거나 이전 설치에서 복사하세요.'
    exit 1
}

Push-Location $backend
try {
    & $venvPython run_worker.py
} finally {
    Pop-Location
}
