<#
이 창에 개발 환경을 켠다.

    . .\activate.ps1        <- 점 하나를 앞에 붙인다

**점(dot sourcing)이 필요하다.** 그냥 `.\activate.ps1` 로 부르면 스크립트가 제
스코프에서 돌고 끝나서, 이 창의 프롬프트와 `deactivate` 함수가 안 남는다. 환경
변수만 process 단위라 살아남으므로 **반쯤 켜진 상태**가 되는데, 그게 가장 헷갈린다.

편집기(VS Code·Cursor)에서는 이걸 부를 필요가 없다 — `.vscode/settings.json` 이
통합 터미널에서 자동으로 켠다.

**켜지 않아도 다 된다.** 이 저장소의 명령·CI·배포 스크립트는 전부
`.\.venv\Scripts\python.exe` 처럼 인터프리터를 직접 가리킨다. 활성화에 기대면
"내 창에서는 되는데 CI 에서는 안 되는" 차이가 생긴다 — 이 스크립트는 편의일 뿐이다.
#>

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$activate = Join-Path $root 'backend\.venv\Scripts\Activate.ps1'

if (-not (Test-Path $activate)) {
    Write-Host ''
    Write-Host "가상환경이 없습니다: $activate" -ForegroundColor Yellow
    Write-Host ''
    Write-Host '만들려면:'
    Write-Host '  cd backend'
    Write-Host '  py -3.13 -m venv .venv'
    Write-Host '  .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt'
    Write-Host ''
    return
}

. $activate

$python = (Get-Command python).Source
$version = & python -c "import sys; print('{}.{}.{}'.format(*sys.version_info[:3]))"

Write-Host ''
Write-Host "  가상환경 : $python (Python $version)"

# **버전이 다르면 말한다.** wheel 의 ABI 태그가 이 버전에 묶이고, 배포 서버가
# 다른 버전이면 패키지를 거절한다 — 그 사실은 배포하는 자리에서야 드러난다.
$wanted = (Get-Content (Join-Path $root '.python-version') -Raw).Trim()
if ($version -notlike "$wanted.*") {
    Write-Host "  경고     : .python-version 은 $wanted 입니다" -ForegroundColor Yellow
}

Write-Host ''
Write-Host '  개발 서버 : cd backend ; python run.py          (8021)'
Write-Host '              cd frontend ; npm run dev           (5200)'
Write-Host '  검증      : cd backend ; ruff check . ; mypy ; pytest ; alembic check'
Write-Host '  끄기      : deactivate'
Write-Host ''
