Param(
    # 릴리스 태그(v0.1.0). 없으면 frontend/package.json 의 version 을 쓴다.
    [string]$Tag
)
<#
배포 패키지(deploy_package.zip)를 만든다.

담기는 것:
    backend\             코드 + requirements.txt
    backend\packages\    wheel 번들 — 서버는 --no-index 로 여기서만 설치한다
    frontend\dist\       빌드된 SPA. 백엔드가 같은 프로세스에서 서빙한다
    run_server.ps1       기동(콘솔) · run_worker.ps1 워커(콘솔)
    tools\WinSW-x64.exe  서비스 래퍼 — service.ps1 이 이것으로 Windows 서비스를 만든다
    pgvector\pg17\       의미 검색용 PostgreSQL 확장 — install_pgvector.ps1 이 넣는다
    deploy.ps1 / rollback.ps1 / venv_sync.ps1 / install.ps1 / precheck.ps1 /
    backup.ps1 / restore.ps1 / service.ps1 / setup_ollama.ps1 /
    build_pgvector.ps1 / install_pgvector.ps1
    배포.md              초기 배포·업데이트 배포 절차
    BUILD_INFO.txt       wheel 을 만든 파이썬 마이너 버전과 릴리스 태그

**배포 스크립트를 패키지에 함께 넣는 이유**: 서버가 릴리스만 받는 환경이어도 zip
하나를 손으로 펼쳐 스크립트를 꺼내면 그다음부터는 그 스크립트가 배포를 처리할 수
있다. 없으면 첫 배포에 저장소를 클론하는 수밖에 없다.
#>

Set-StrictMode -Version Latest

# ErrorActionPreference 를 'Stop' 으로 두지 않는다. Windows PowerShell 5.1 은
# 네이티브 명령이 stderr 에 쓰기만 해도 그것을 오류 레코드로 감싸는데, Stop 이면
# pip 의 단순 경고 한 줄에도 패키징이 멈춘다. 대신 native 호출마다 $LASTEXITCODE 를
# 직접 확인한다 — 아래 모든 호출이 그렇게 돼 있다.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location (Join-Path $root '..\..')

Write-Host '배포 패키지 생성 (Windows)'

<#
**wheel 을 만들 파이썬을 PATH 에 맡기지 않는다.**

바이너리 wheel 은 ABI 태그(cp313)를 달고 있어 다른 마이너 버전에는 설치되지
않는다. 그런데 개발 PC 의 PATH 에는 대개 다른 버전이 앞에 있고, 그러면 **서버가
거절할 패키지가 조용히 만들어진다** — 그 사실은 배포하는 자리에서야 드러난다.
실측: 이 저장소를 처음 패키징했을 때 .python-version 은 3.13 인데 PATH 의
python 이 3.12 라 cp312 wheel 이 담겼다.

`.python-version` 을 읽어 py 런처로 그 버전을 집는다. 못 찾으면 **여기서 멈춘다** —
틀린 패키지를 만드는 것보다 낫다.
#>
$wantedPython = (Get-Content .\.python-version -Raw).Trim()
$py = $null
try {
    $resolved = & py "-$wantedPython" -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $resolved) { $py = $resolved.Trim() }
} catch { }
if (-not $py) {
    Write-Error "Python $wantedPython 을 찾지 못했습니다 (py -0p 로 목록 확인). wheel 의 ABI 태그가 이 버전에 묶이므로 다른 버전으로 만들면 서버가 거절합니다."
    exit 1
}
Write-Host "wheel 을 만들 파이썬: $py (요구: $wantedPython)"

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .\deploy
New-Item -ItemType Directory -Path .\deploy | Out-Null

Write-Host '백엔드 코드 복사'
Copy-Item -Recurse -Force .\backend .\deploy\backend
# 개발 산출물은 패키지에서 뺀다. 운영 데이터(.env·filestore·logs)는 서버의
# <AppPath>_data 에 있으므로 애초에 여기 없다.
foreach ($junk in @('.venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'logs', 'filestore', '.env')) {
    Get-ChildItem -Path .\deploy\backend -Filter $junk -Recurse -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# --- 프론트엔드 ---------------------------------------------------------------
# 백엔드가 <패키지 루트>\frontend\dist 에서 SPA 를 서빙한다. **이게 없으면 배포된
# 앱이 모든 페이지에 API 의 JSON 404 를 돌려준다** — 라우팅 버그처럼 보인다.
Write-Host '프론트엔드 빌드'
Push-Location .\frontend
$env:NODE_OPTIONS = '--max-old-space-size=4096'
npm ci
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "npm ci 실패 (exit $LASTEXITCODE)"; exit 1 }
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "npm run build 실패 (exit $LASTEXITCODE)"; exit 1 }
Pop-Location

if (-not (Test-Path .\frontend\dist\index.html)) {
    Write-Error '프론트엔드 빌드에 dist\index.html 이 없습니다.'
    exit 1
}

# 프론트는 API 절대주소를 굽지 않는다(항상 상대경로 /api). 굽는 방식이면 값이
# 빠졌을 때 **사용자 브라우저가 자기 PC 를 부른다** — 그런 흔적이 남아 있지 않은지
# 확인한다.
$leaked = Get-ChildItem .\frontend\dist\assets -Filter '*.js' -ErrorAction SilentlyContinue |
    Where-Object { Select-String -Path $_.FullName -Pattern '127.0.0.1:80' -Quiet -SimpleMatch }
if ($leaked) {
    Write-Error "번들에 개발 서버 주소가 남아 있습니다 ($($leaked[0].Name)). API 주소를 굽지 않도록 고치세요."
    exit 1
}
Write-Host '프론트엔드 API 주소 검사 통과'

New-Item -ItemType Directory -Force -Path .\deploy\frontend | Out-Null
Copy-Item -Recurse -Force .\frontend\dist .\deploy\frontend\dist

# --- 카탈로그 원천 -------------------------------------------------------------
# 계열·기종·물성·시험법은 코드가 아니라 **데이터**라 마이그레이션으로 안 간다. 서버에서
# `scripts\import_catalog.py` 를 돌려야 들어가고, 그 스크립트는 <AppPath>\source\catalog 를
# 읽는다 — 패키지에 없으면 폐쇄망에서는 들일 길이 없다. 쪽 이미지(pages)와 PDF 는
# 반입이 안 읽으므로 뺀다(수백 MB). 배포는 이것을 자동으로 돌리지 않는다: 반입은 멱등이고
# 있는 값을 안 덮지만, 언제 들일지는 사람이 정한다.
Write-Host '카탈로그 원천 복사 (source\catalog · source\materialtwin)'
New-Item -ItemType Directory -Force -Path .\deploy\source\catalog | Out-Null
# **proposals 가 빠지면 검토함이 한 물음만 선다.** 후보·추천·근거와 개발에서 내린 결정이 거기
# 있어서, 없으면 운영은 「규격의 시험 항목」(정본 없이 서는 유일한 물음)만 보고 나머지 아홉은
# 빈 채로 — 그리고 개발에서 고른 것을 운영이 다시 묻는다. 운영 첫 반입에서 실측(2026-09-16).
foreach ($part in @('equipment', 'ontology', 'proposals', 'schema.json', 'sources.json', 'urls.json', 'reference_docs.json', 'graph.json', 'index.md', 'README.md', 'build_graph.py')) {
    Copy-Item -Recurse -Force (Join-Path .\source\catalog $part) (Join-Path .\deploy\source\catalog $part)
}
Copy-Item -Recurse -Force .\source\materialtwin .\deploy\source\materialtwin

# --- wheel 번들 ---------------------------------------------------------------
# 패키지에 설치하는 대신 wheel 을 모아 담는다. 서버가 `pip install --no-index
# --find-links=packages` 로 진짜 가상환경을 만들므로 **배포가 네트워크를 쓰지 않는다.**
& $py -m pip install --upgrade pip

$wheelDir = '.\deploy\backend\packages'
Write-Host 'wheel 번들 생성'
& $py -m pip wheel -r .\deploy\backend\requirements.txt -w $wheelDir
if ($LASTEXITCODE -ne 0) { Write-Error "pip wheel 실패 (exit $LASTEXITCODE)"; exit 1 }

$wheels = Get-ChildItem -Path $wheelDir -Filter '*.whl' -ErrorAction SilentlyContinue
# **가상환경을 만들 수 없는 번들을 출하하느니 빌드를 실패시킨다.**
#
# httpx 가 여기 있는 이유는 앱이 아니라 스크립트 때문이다. `fastapi.testclient` 가
# 그것을 요구하는데, 개발 전용 의존성에만 있으면 앱은 멀쩡히 뜨고 **운영 서버에서
# 스크립트만 안 돈다.**
foreach ($mod in @('fastapi', 'uvicorn', 'sqlalchemy', 'alembic', 'psycopg', 'bcrypt', 'pyjwt', 'httpx')) {
    $needle = ($mod -replace '_', '-')
    if (-not ($wheels | Where-Object { ($_.Name -replace '_', '-') -like "$needle-*" })) {
        Write-Error "packages 에 '$mod' wheel 이 없습니다."
        exit 1
    }
}
Write-Host "  wheel $($wheels.Count) 개, 의존성 검사 통과"

# --- MCP 서버 ------------------------------------------------------------------
# **앱과 별도 venv 라 wheel 도 따로 담는다.** MCP 가 없어도 앱은 돌아야 하므로
# 여기서 실패해도 패키징은 계속된다 — 다만 조용히 넘어가지 않고 경고를 남긴다.
if (Test-Path .\mcp_server\server.py) {
    Write-Host 'MCP 서버 포함'
    New-Item -ItemType Directory -Force -Path .\deploy\mcp_server\guide | Out-Null
    Copy-Item -Force .\mcp_server\server.py .\deploy\mcp_server\server.py
    # **server.py 가 import 하는 제 옆 모듈도 담는다.** 빠지면 서비스가 ImportError 로
    # 즉시 죽고, WinSW 가 되살리다 무한 재시작에 빠진다 — 그 증상은 로그를 열기 전까지
    # 「서비스가 STOPPED」 로만 보인다(운영 실측 2026-09-23, v0.15.0~v0.17.0 세 판이 그랬다).
    # 새 모듈을 더하면 여기에도 더한다 — 잊으면 test_mcp_tools.py 가 잡는다.
    Copy-Item -Force .\mcp_server\calltrace.py .\deploy\mcp_server\calltrace.py
    Copy-Item -Force .\mcp_server\merge.py .\deploy\mcp_server\merge.py
    Copy-Item -Force .\mcp_server\requirements.txt .\deploy\mcp_server\requirements.txt
    Copy-Item -Force .\mcp_server\README.md .\deploy\mcp_server\README.md
    Copy-Item -Force .\mcp_server\guide\GUIDE.md .\deploy\mcp_server\guide\GUIDE.md

    & $py -m pip wheel -r .\deploy\mcp_server\requirements.txt -w .\deploy\mcp_server\packages
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'MCP wheel 번들을 만들지 못했습니다 — 이 패키지로는 MCP 서버가 안 뜹니다(앱은 정상).'
    } else {
        $mcpWheels = (Get-ChildItem .\deploy\mcp_server\packages -Filter '*.whl' -ErrorAction SilentlyContinue).Count
        Write-Host "  MCP wheel $mcpWheels 개"
    }
}

# --- 서비스 래퍼 (WinSW) --------------------------------------------------------
# 부팅 때 뜨고 죽으면 되살아나는 것은 Windows 서비스가 해 주는데, 콘솔 프로그램을 서비스로
# 감싸는 것이 WinSW 다(MIT). **저장소에 넣지 않고 패키징 때 받는다** — 18MB 바이너리를
# git 에 두면 클론이 무거워지고 판을 올릴 때마다 또 쌓인다. 대신 판과 해시를 여기 못
# 박아, 받은 파일이 그 판이 아니면 패키징을 멈춘다. self-contained 빌드라 서버에 .NET 을
# 깔 필요가 없다 — 폐쇄망 서버의 OS 판을 묻지 않아도 된다.
#
# **없으면 실패시킨다.** 「파일은 담고 띄우는 법은 안 담는 것」 다음으로 나쁜 것이 「띄우는
# 법은 담고 파일은 안 담는 것」 이다 — 서버에서 service.ps1 이 exe 를 못 찾는다.
$winswVersion = 'v2.12.0'
$winswSha256 = '05B82D46AD331CC16BDC00DE5C6332C1EF818DF8CEEFCD49C726553209B3A0DA'
$winswUrl = "https://github.com/winsw/winsw/releases/download/$winswVersion/WinSW-x64.exe"
$toolsDir = '.\deploy\tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$winswPath = Join-Path $toolsDir 'WinSW-x64.exe'
# 개발 PC 에서 되풀이할 때 매번 받지 않게 옆에 캐시한다(.gitignore 의 deploy* 에 걸린다).
$winswCache = ".\deploy_cache\WinSW-$winswVersion-x64.exe"
if (-not (Test-Path $winswCache)) {
    Write-Host "WinSW $winswVersion 다운로드"
    New-Item -ItemType Directory -Force -Path (Split-Path $winswCache) | Out-Null
    try {
        Invoke-WebRequest -Uri $winswUrl -OutFile $winswCache -UseBasicParsing
    } catch {
        Write-Error "WinSW 를 받지 못했습니다: $winswUrl — $_"
        exit 1
    }
}
$actualHash = (Get-FileHash $winswCache -Algorithm SHA256).Hash
if ($actualHash -ne $winswSha256) {
    Remove-Item -Force $winswCache
    Write-Error "WinSW 해시가 다릅니다 (기대 $winswSha256, 실제 $actualHash). 판이 바뀌었거나 받다 깨졌습니다 — 패키징을 멈춥니다."
    exit 1
}
Copy-Item -Force $winswCache $winswPath
Write-Host "  WinSW $winswVersion 확인 (sha256 일치)"

# --- 스크립트와 빌드 정보 ------------------------------------------------------
Write-Host '실행·배포 스크립트 추가'
Copy-Item -Force .\scripts\ci\run_server_template.ps1 .\deploy\run_server.ps1
Copy-Item -Force .\scripts\ci\run_worker_template.ps1 .\deploy\run_worker.ps1
# MCP 를 담은 패키지에만 넣는다. **파일은 담고 띄우는 법은 안 담는 것**이 제일
# 나쁘다 — 받는 쪽은 폴더만 보고 어떻게 쓰는지 알 수 없다(실측: 첫 패키지가 그랬다).
if (Test-Path .\deploy\mcp_server\server.py) {
    Copy-Item -Force .\scripts\ci\run_mcp_template.ps1 .\deploy\run_mcp.ps1
}
Copy-Item -Force .\scripts\deploy\venv_sync.ps1 .\deploy\venv_sync.ps1
Copy-Item -Force .\scripts\deploy\deploy.ps1 .\deploy\deploy.ps1
Copy-Item -Force .\scripts\deploy\rollback.ps1 .\deploy\rollback.ps1
Copy-Item -Force .\scripts\deploy\install.ps1 .\deploy\install.ps1
Copy-Item -Force .\scripts\deploy\precheck.ps1 .\deploy\precheck.ps1
Copy-Item -Force .\scripts\deploy\backup.ps1 .\deploy\backup.ps1
Copy-Item -Force .\scripts\deploy\restore.ps1 .\deploy\restore.ps1
Copy-Item -Force .\scripts\deploy\service.ps1 .\deploy\service.ps1
Copy-Item -Force .\scripts\deploy\setup_ollama.ps1 .\deploy\setup_ollama.ps1
Copy-Item -Force .\scripts\deploy\build_pgvector.ps1 .\deploy\build_pgvector.ps1
Copy-Item -Force .\scripts\deploy\install_pgvector.ps1 .\deploy\install_pgvector.ps1
# pgvector 산출물(판별 폴더). 저장소에 함께 둔 것을 그대로 담는다 — 폐쇄망이 zip 하나로 받는다.
Copy-Item -Recurse -Force .\scripts\deploy\pgvector .\deploy\pgvector

# 배포 문서도 함께 넣는다. 폐쇄망 서버는 zip 하나만 받으므로, 문서가 저장소에만
# 있으면 **정작 설치하는 자리에서 볼 수 없다.**
Copy-Item -Force .\배포.md .\deploy\배포.md

# 바이너리 wheel 은 ABI 태그(cp313 등)를 달고 있어 다른 마이너 버전에는 설치되지
# 않는다. deploy.ps1 이 이 값을 서버 파이썬과 비교한다.
$buildPython = & $py -c "import sys; print('{}.{}'.format(sys.version_info[0], sys.version_info[1]))"
if ($LASTEXITCODE -ne 0) { Write-Error '빌드 파이썬 버전을 확인하지 못했습니다'; exit 1 }
if ($buildPython -ne $wantedPython) {
    Write-Error "고른 파이썬이 $buildPython 입니다 (.python-version 은 $wantedPython). 패키징을 멈춥니다."
    exit 1
}
Write-Host "빌드 파이썬 기록: $buildPython"

# **패키지가 자기 버전을 들고 있어야 한다.** 배포한 뒤 "서버에 뭐가 깔렸나" 를
# 물으면 답할 데가 있어야 하는데, 태그 없이 배포하면 되짚을 방법이 아예 없다.
if (-not $Tag) {
    $Tag = 'v' + (node -p "require('./frontend/package.json').version")
    if ($LASTEXITCODE -ne 0) { Write-Error '버전을 읽지 못했습니다'; exit 1 }
}
Write-Host "패키지 버전: $Tag"
Set-Content -Encoding utf8 -Path .\deploy\BUILD_INFO.txt -Value @(
    "python=$buildPython"
    "version=$Tag"
)

# --- zip ---------------------------------------------------------------------
Write-Host 'zip 생성'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$deployDir = (Resolve-Path .\deploy).Path
$zipPath = Join-Path $deployDir 'deploy_package.zip'
# 압축 대상 폴더 안에 직접 만들면 아카이브가 자기 자신을 담으려다 실패한다.
$stagingZip = Join-Path ([System.IO.Path]::GetDirectoryName($deployDir)) 'deploy_package.zip'
Remove-Item -Force -ErrorAction SilentlyContinue $stagingZip
[System.IO.Compression.ZipFile]::CreateFromDirectory($deployDir, $stagingZip)
Move-Item -Force $stagingZip $zipPath

if (Test-Path $zipPath) {
    $sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host "패키지 완료: $zipPath (${sizeMb}MB)"
} else {
    Write-Error "패키지 생성 실패: $zipPath"
    exit 1
}
Pop-Location
