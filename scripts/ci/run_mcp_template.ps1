Param()
<#
배포된 MCP 서버의 기동 스크립트.

    cd <AppPath>
    .\run_mcp.ps1

**두 번째 창이다.** AI 가 시험 역량을 직접 묻고 카탈로그를 채우는 자리이고, 없어도
앱은 멀쩡히 돈다 — 이 창이 꺼져 있으면 AI 쪽에서 「연결할 수 없다」 가 뜰 뿐이다.

**설정은 `backend\.env` 한 곳에서 읽는다.** 창을 띄울 때마다 환경변수를 손으로 주게
두면 언젠가 빠뜨리고, 그때 도구가 전부 실패한다(주소가 틀려서). 백엔드 Settings 는
모르는 키를 무시하므로 같은 파일에 둬도 안전하다.

    PORT=8020            ← 백엔드 포트. MCP 가 이 값으로 API 주소를 맞춘다
    MCP_PORT=8030        ← 이 서버가 들을 포트 (기본 8030)
    MCP_HOST=127.0.0.1   ← 밖에 열려면 0.0.0.0

**백엔드와 다른 가상환경을 쓴다.** MCP SDK 가 언제든 프레임워크 판을 올릴 수 있고,
그때 앱이 인질이 되면 안 된다. `_venvs\mcp_server` 는 deploy.ps1 이 만든다.
#>

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path ($scriptDir + '_venvs') 'mcp_server\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Error "MCP 가상환경이 없습니다: $venvPython — deploy.ps1 을 다시 실행하세요(그때 만들어집니다)."
    exit 1
}

$serverDir = Join-Path $scriptDir 'mcp_server'
if (-not (Test-Path (Join-Path $serverDir 'server.py'))) {
    Write-Error 'mcp_server\server.py 를 찾을 수 없습니다. 패키지가 불완전합니다.'
    exit 1
}

# --- .env 읽기 ----------------------------------------------------------------
# 이미 환경변수가 있으면 그것이 이긴다 — 한 번만 다르게 띄우는 길을 막지 않는다.
$envFile = Join-Path $scriptDir 'backend\.env'
function Read-EnvValue([string]$name) {
    if (-not (Test-Path $envFile)) { return $null }
    $line = Select-String -Path $envFile -Pattern ("^\s*" + $name + "\s*=\s*(.+)$") | Select-Object -First 1
    if (-not $line) { return $null }
    return $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
}

if (-not $env:TESTATLAS_API_BASE) {
    $backendPort = Read-EnvValue 'PORT'
    if (-not $backendPort) { $backendPort = '8020' }
    $env:TESTATLAS_API_BASE = "http://127.0.0.1:$backendPort/api"
}
$mcpPort = Read-EnvValue 'MCP_PORT'
if (-not $mcpPort) { $mcpPort = '8030' }
$mcpHost = Read-EnvValue 'MCP_HOST'
if (-not $mcpHost) { $mcpHost = '127.0.0.1' }

# 백엔드가 살아 있는지 먼저 본다. 안 떠 있으면 도구가 전부 실패하는데, 그 사실은
# 도구를 불러야 드러나므로 여기서 말해 준다.
try {
    $health = Invoke-RestMethod -Uri ($env:TESTATLAS_API_BASE + '/health') -TimeoutSec 3
    Write-Host "백엔드 $($env:TESTATLAS_API_BASE) — $($health.status) $($health.version)"
} catch {
    Write-Warning "백엔드에 닿지 못했습니다($($env:TESTATLAS_API_BASE)). run_server.ps1 을 먼저 띄우세요."
}

# 포트를 이미 쓰고 있으면 **거절한다.** 안 그러면 옛 프로세스가 낡은 코드로 응답하는
# 것을 모른 채 헤맨다 — 개발에서 실제로 그렇게 반나절을 썼다(run.py 주석 참고).
$owner = (Get-NetTCPConnection -State Listen -LocalPort ([int]$mcpPort) -ErrorAction SilentlyContinue).OwningProcess
if ($owner) {
    Write-Error "포트 $mcpPort 를 이미 쓰고 있습니다(PID $owner). 먼저 멈추세요: Stop-Process -Id $owner -Force"
    exit 1
}

$env:FASTMCP_PORT = "$mcpPort"
$env:FASTMCP_HOST = "$mcpHost"
Write-Host "MCP ${mcpHost}:${mcpPort} — 등록 주소 http://<서버>:$mcpPort/mcp"
Write-Host '개인 토큰은 화면의 「내 정보 → 토큰」 에서 발급합니다(범위: read · catalog:write).'

Push-Location $serverDir
try {
    & $venvPython -c "import server; server.mcp.run(transport='http')"
} finally {
    Pop-Location
}
