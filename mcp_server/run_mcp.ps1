Param(
    [int]$Port = 0,
    [string]$BindHost,
    [string]$ApiBase,
    [switch]$Stdio,
    [switch]$ReadOnly,
    [switch]$Trace
)
<#
개발 중 MCP 서버 기동.

    cd mcp_server
    .
un_mcp.ps1

**포트를 외우지 않는다.** `backend\.env` 한 곳에서 읽는다 — PORT 로 백엔드 주소를
맞추고(개발은 그 값 +1, 운영 설치는 그 값), MCP_PORT·MCP_HOST 로 제가 들을 자리를
정한다. 주소가 다르면 도구가 전부 「백엔드에 닿지 못했습니다」 로 실패하는데, 그때
원인을 찾는 데 시간이 든다.

**운영(`scripts\deploy\service.ps1`)과 같은 키를 읽는다.** 같은 `MCP_PORT` 가 개발에서만
무시되면, 개발에서 되던 설정이 운영에서 달라지고 그것은 더 찾기 어렵다.

가상환경이 없으면 만들고 의존성까지 넣는다. **backend\.venv 와 섞지 않는다** —
MCP SDK 가 언제든 프레임워크 판을 올릴 수 있고, 그때 앱이 인질이 되면 안 된다.

    .
un_mcp.ps1 -Port 8031        다른 포트로
    .
un_mcp.ps1 -ApiBase '...'    백엔드 주소를 직접
    .
un_mcp.ps1 -Stdio            개인 연결(stdio) — HTTP 대신
    -ReadOnly 를 주면 읽기 도구만 싣는다(39개 · 목록 절반).
    -Trace 를 주면 도구 호출 자취를 logs\calls.jsonl 에 남긴다 — eval\score.py 의 재료.
    -BindHost 0.0.0.0 으로 밖에 연다(기본은 .env 의 MCP_HOST, 없으면 127.0.0.1).
#>

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $here
$venvPython = Join-Path $here '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host '가상환경이 없습니다 — 만듭니다(backend 와 별도).'
    & py -m venv (Join-Path $here '.venv')
    if ($LASTEXITCODE -ne 0) { throw "가상환경을 만들지 못했습니다 (exit $LASTEXITCODE)" }
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet -r (Join-Path $here 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "의존성 설치 실패 (exit $LASTEXITCODE)" }
    Write-Host '  준비됐습니다.'
}

# --- backend\.env 를 한 번만 읽는다 --------------------------------------------
# `^\s*PORT` 는 앵커가 있어 MCP_PORT 줄에 걸리지 않는다. 백엔드 Settings 는 모르는 키를
# 무시하므로(extra="ignore") MCP_* 를 같은 파일에 둬도 안전하다 — 배포판도 같은 자리를 본다.
$envFile = Join-Path $repo 'backend\.env'
$backendPort = 8020
$isDev = $true
$envMcpPort = 0
$envMcpHost = ''
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*PORT\s*=\s*(\d+)') { $backendPort = [int]$Matches[1] }
        if ($line -match '^\s*APP_ENV\s*=\s*(\w+)') { $isDev = ($Matches[1] -eq 'development') }
        if ($line -match '^\s*MCP_PORT\s*=\s*(\d+)') { $envMcpPort = [int]$Matches[1] }
        if ($line -match '^\s*MCP_HOST\s*=\s*(\S+)') { $envMcpHost = $Matches[1].Trim('"').Trim("'") }
    }
}

# --- 백엔드 주소 --------------------------------------------------------------
if (-not $ApiBase) {
    # run.py 가 개발에서 PORT+1 을 쓴다. 그 규칙을 여기서도 따른다.
    if ($isDev) { $backendPort = $backendPort + 1 }
    $ApiBase = "http://127.0.0.1:$backendPort/api"
}
$env:TESTSCOPE_API_BASE = $ApiBase
Write-Host "백엔드: $ApiBase"

# 도구 목록은 매 턴 통째로 실린다 — 읽기만 쓰는 연결에 쓰기 도구 스물넷을 보여 줄
# 이유가 없다(어차피 범위가 없으면 403 이다).
$env:TESTSCOPE_MCP_TOOLS = if ($ReadOnly) { 'read' } else { 'all' }
if ($ReadOnly) { Write-Host '도구: 읽기만' }

# 자취 — AI 가 무엇을 어떤 순서로 빈손으로 몇 번 불렀나. 측정(eval)할 때 켠다.
if ($Trace) { $env:TESTSCOPE_MCP_TRACE = '1'; Write-Host '자취: logs\calls.jsonl' }

if ($Stdio) {
    & $venvPython (Join-Path $here 'server.py')
    exit $LASTEXITCODE
}

# **8022 다, 8030 이 아니다.** 8030 은 CrossAXTF 의 운영 포트라 같은 PC 에서 겹쳤다
# (2026-09-12 실측 — 이 PC 에서 이 MCP 가 127.0.0.1:8030 을 잡고 있었다). 「플랫폼마다
# 10씩」 규칙대로 TestScope 대역(802x) 안에서 백엔드 +2 다.
# 순서: 인자 > backend\.env > 기본값. 운영 service.ps1 도 같은 두 키를 같은 순서로 본다.
if ($Port -eq 0) { if ($envMcpPort -ne 0) { $Port = $envMcpPort } else { $Port = 8022 } }
if (-not $BindHost) { if ($envMcpHost) { $BindHost = $envMcpHost } else { $BindHost = '127.0.0.1' } }
Write-Host "MCP: http://${BindHost}:$Port/mcp"
# `python -c` 는 **부른 자리**를 sys.path 에 얹는다 — 저장소 뿌리에서 부르면 URL 까지
# 찍어 놓고 `ModuleNotFoundError: server` 로 죽는다. 배포판(run_mcp_template.ps1)처럼
# 자리를 옮겨 두고 부른다.
Push-Location $here
try {
    # 공식 mcp SDK(2.x)다 — 전송 이름은 'streamable-http' 이고 host·port 는 인자로 받는다.
    # 'http' 와 FASTMCP_PORT 환경변수는 다른 패키지(fastmcp)의 것이라 여기서는 통하지 않는다.
    & $venvPython -c "import server; server.mcp.run(transport='streamable-http', host='$BindHost', port=$Port)"
} finally {
    Pop-Location
}
exit $LASTEXITCODE
