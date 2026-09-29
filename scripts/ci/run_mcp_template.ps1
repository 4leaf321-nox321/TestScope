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
    MCP_PORT=8022        ← 이 서버가 들을 포트 (기본 8022 — 백엔드 +2)
    MCP_HOST=127.0.0.1   ← 밖에 열려면 0.0.0.0
    MCP_ALLOWED_HOSTS=   ← 밖에 열 때 **필수**. 없으면 서버가 기동을 거절한다

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

if (-not $env:TESTSCOPE_API_BASE) {
    $backendPort = Read-EnvValue 'PORT'
    if (-not $backendPort) { $backendPort = '8020' }
    $env:TESTSCOPE_API_BASE = "http://127.0.0.1:$backendPort/api"
}
$mcpPort = Read-EnvValue 'MCP_PORT'
if (-not $mcpPort) { $mcpPort = '8022' }
$mcpHost = Read-EnvValue 'MCP_HOST'
if (-not $mcpHost) { $mcpHost = '127.0.0.1' }
$mcpAllowed = Read-EnvValue 'MCP_ALLOWED_HOSTS'

# 백엔드가 살아 있는지 먼저 본다. 안 떠 있으면 도구가 전부 실패하는데, 그 사실은
# 도구를 불러야 드러나므로 여기서 말해 준다.
try {
    $health = Invoke-RestMethod -Uri ($env:TESTSCOPE_API_BASE + '/health') -TimeoutSec 3
    # **이 주소는 안쪽이다.** MCP 서버가 같은 기계의 백엔드를 부르는 자리라 늘
    # 127.0.0.1 이고, 사람이 등록에 적을 주소가 아니다 — 아래 「등록 주소」 와 붙어
    # 있어서 그것으로 읽힌 적이 있다(2026-09-29).
    Write-Host "백엔드(이 기계 안) $($env:TESTSCOPE_API_BASE) — $($health.status) $($health.version)"
} catch {
    Write-Warning "백엔드에 닿지 못했습니다($($env:TESTSCOPE_API_BASE)). run_server.ps1 을 먼저 띄우세요."
}

# 포트를 이미 쓰고 있으면 **거절한다.** 안 그러면 옛 프로세스가 낡은 코드로 응답하는
# 것을 모른 채 헤맨다 — 개발에서 실제로 그렇게 반나절을 썼다(run.py 주석 참고).
$owner = (Get-NetTCPConnection -State Listen -LocalPort ([int]$mcpPort) -ErrorAction SilentlyContinue).OwningProcess
if ($owner) {
    Write-Error "포트 $mcpPort 를 이미 쓰고 있습니다(PID $owner). 먼저 멈추세요: Stop-Process -Id $owner -Force"
    exit 1
}

# **듣는 자리와 붙는 주소는 다르다.** 0.0.0.0 은 바인딩이지 주소가 아니라서, 그대로
# 찍으면 그걸 등록에 붙여 넣는 사람이 나온다. 허용 Host 를 적어 뒀으면 그 첫 줄이 곧
# 사람들이 쓸 주소다 — 서버가 Host 헤더를 그것과 글자 그대로 견주기 때문이다.
$shown = if ($mcpAllowed) { ($mcpAllowed -split ',')[0].Trim() }
         elseif ($mcpHost -eq '0.0.0.0') { "<서버>:$mcpPort" }
         else { "${mcpHost}:${mcpPort}" }

Write-Host "MCP: ${mcpHost}:${mcpPort} 에서 듣습니다"
Write-Host "등록 주소  http://$shown/mcp"
Write-Host ("등록      claude mcp add --transport http testscope http://$shown/mcp " +
    "--header 'Authorization: Bearer <내 개인 토큰>'")
Write-Host '개인 토큰은 화면의 「내 정보 → 토큰」 에서 각자 발급합니다(쓰기는 범위를 함께 고릅니다).'
if ($mcpHost -ne '127.0.0.1' -and $mcpHost -ne 'localhost') {
    if (-not $mcpAllowed) {
        Write-Warning 'MCP_HOST 를 밖으로 열었는데 MCP_ALLOWED_HOSTS 가 없습니다 — 서버가 기동을 거절합니다.'
    }
    # 방화벽은 install.ps1 이 열지만, .env 를 나중에 고친 서버에는 규칙이 없다.
    $rule = Get-NetFirewallRule -DisplayName "TestScope MCP $mcpPort" -ErrorAction SilentlyContinue
    if (-not $rule) {
        Write-Warning "방화벽에 TCP $mcpPort 규칙이 안 보입니다 — 밖에서 못 붙으면 이것부터 보십시오:"
        Write-Warning "  New-NetFirewallRule -DisplayName 'TestScope MCP $mcpPort' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $mcpPort"
    }
}

Push-Location $serverDir
try {
    # **server.py 의 main() 이 전송·바인딩·허용 Host 를 정한다.** 개발용
    # mcp_server\run_mcp.ps1 과 서비스 정의도 같은 자리를 지난다 — 셋이 각자 적으면
    # 한 곳만 고쳤을 때 갈라지고, 갈라진 쪽만 조용히 보호 없이 뜬다.
    # 설정은 server.py 가 backend\.env 에서 직접 읽는다(환경변수가 비어 있을 때만).
    & $venvPython server.py
} finally {
    Pop-Location
}
