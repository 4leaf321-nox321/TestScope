Param(
    [int]$Port = 0,
    [string]$ApiBase,
    [switch]$Stdio
)
<#
개발 중 MCP 서버 기동.

    cd mcp_server
    .
un_mcp.ps1

**백엔드 포트를 외우지 않는다.** `backend\.env` 의 PORT 를 읽어 API 주소를 스스로
맞춘다(개발은 그 값 +1, 운영 설치는 그 값) — 다르면 도구가 전부 「백엔드에 닿지
못했습니다」 로 실패하는데, 그때 원인을 찾는 데 시간이 든다.

가상환경이 없으면 만들고 의존성까지 넣는다. **backend\.venv 와 섞지 않는다** —
MCP SDK 가 언제든 프레임워크 판을 올릴 수 있고, 그때 앱이 인질이 되면 안 된다.

    .
un_mcp.ps1 -Port 8031        다른 포트로
    .
un_mcp.ps1 -ApiBase '...'    백엔드 주소를 직접
    .
un_mcp.ps1 -Stdio            개인 연결(stdio) — HTTP 대신
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

# --- 백엔드 주소 --------------------------------------------------------------
if (-not $ApiBase) {
    $envFile = Join-Path $repo 'backend\.env'
    $backendPort = 8020
    $isDev = $true
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*PORT\s*=\s*(\d+)') { $backendPort = [int]$Matches[1] }
            if ($line -match '^\s*APP_ENV\s*=\s*(\w+)') { $isDev = ($Matches[1] -eq 'development') }
        }
    }
    # run.py 가 개발에서 PORT+1 을 쓴다. 그 규칙을 여기서도 따른다.
    if ($isDev) { $backendPort = $backendPort + 1 }
    $ApiBase = "http://127.0.0.1:$backendPort/api"
}
$env:TESTSCOPE_API_BASE = $ApiBase
Write-Host "백엔드: $ApiBase"

if ($Stdio) {
    & $venvPython (Join-Path $here 'server.py')
    exit $LASTEXITCODE
}

if ($Port -eq 0) { $Port = 8030 }
$env:FASTMCP_PORT = "$Port"
Write-Host "MCP: http://127.0.0.1:$Port/mcp"
& $venvPython -c "import server; server.mcp.run(transport='http')"
exit $LASTEXITCODE
