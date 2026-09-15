<#
Windows 서비스 등록 — 부팅하면 뜨고, 죽으면 되살아난다.

콘솔(run_server.ps1)로 띄운 앱은 창을 닫으면 멈추고 서버를 재부팅하면 사람이 다시
켜야 한다. 서비스로 두면 로그인 없이 부팅 때 올라오고, 프로세스가 사라지면 서비스
관리자가 되살린다. 그 일을 WinSW(https://github.com/winsw/winsw, MIT)가 한다 —
패키지에 동봉된 단일 실행 파일(tools\WinSW-x64.exe, .NET 포함 self-contained 라 서버에
아무것도 깔 필요가 없다). 폐쇄망도 zip 하나로 된다.

    <AppPath>_service\TestScope.exe        WinSW 복사본 — 서비스의 실행 파일
    <AppPath>_service\TestScope.xml        무엇을 어떻게 띄우나
    <AppPath>_service\TestScope-MCP.*      MCP 서버(패키지에 있을 때만)
    <AppPath>_data\logs\service\           서비스 래퍼의 stdout/stderr (앱 로그는 logs\ 에 그대로)

**앱 폴더 밖(_service)에 둔다.** deploy.ps1 이 <AppPath> 를 통째로 _prev 로 옮기므로,
서비스 실행 파일이 그 안에 있으면 배포마다 서비스가 깨진 경로를 가리킨다.
_venvs·_data 와 같은 자리다.

서비스가 띄우는 것은 run_server.ps1 이 아니라 **가상환경의 python.exe 가 직접** run.py 다.
PowerShell 을 사이에 두면 멈출 때 자식 프로세스가 남는 일이 있고, 그러면 다음 기동이
「포트에 이미 응답하는 서버가 있다」 로 거절된다(run.py 주석).

사용:
  .\service.ps1 -AppPath 'C:\Server\TestScope'                      # 등록(있으면 갱신)하고 시작
  .\service.ps1 -AppPath 'C:\Server\TestScope' -Action status
  .\service.ps1 -AppPath 'C:\Server\TestScope' -Action stop         # 콘솔로 띄워 볼 때
  .\service.ps1 -AppPath 'C:\Server\TestScope' -Action uninstall
  .\service.ps1 -AppPath 'C:\Server\TestScope' -NoMcp               # 백엔드만

관리자 PowerShell 에서 실행한다. install.ps1 이 마지막 단계로 이것을 부른다.
#>

param(
    [Parameter(Mandatory = $true)][string]$AppPath,
    [ValidateSet('install', 'uninstall', 'start', 'stop', 'restart', 'status')]
    [string]$Action = 'install',
    [switch]$NoMcp
)

$ErrorActionPreference = 'Stop'

function Assert-NotFlag([string]$value, [string]$name) {
    if ($value -and $value.StartsWith('-')) {
        throw @"
-$name 값이 '$value' 입니다 — 대시를 두 번 쓰신 것 같습니다.

PowerShell 매개변수는 대시가 하나입니다:  -$name '<값>'
'--$name' 처럼 쓰면 그 글자 자체가 값이 되고, 뒤에 적은 진짜 값은 다른
매개변수로 밀려 들어갑니다. 아무것도 실행하지 않았습니다.
"@
    }
}
Assert-NotFlag $AppPath 'AppPath'
function Write-Log([string]$m) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $m" }

<#
네이티브 명령 실행 — stderr 를 오류로 착각하지 않는다. WinSW 는 진행 로그를 stderr 로
내므로, 5.1 의 Stop 상태에서 그대로 부르면 정상 등록이 실패로 뒤집힌다. 종료 코드로만
판정한다.
#>
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FailureMessage,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Command
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($code -ne 0) { throw "$FailureMessage (exit $code)" }
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and $Action -ne 'status') {
    throw '서비스 등록·제어는 관리자 PowerShell 에서 해야 합니다.'
}

$serviceDir = $AppPath + '_service'
$dataPath = $AppPath + '_data'
$venvs = $AppPath + '_venvs'
$logDir = Join-Path $dataPath 'logs\service'
$winsw = Join-Path $AppPath 'tools\WinSW-x64.exe'

# .env 는 접속 정보라 서비스 정의에 복사하지 않는다 — 앱이 제 자리에서 읽는다.
# MCP 만 백엔드 포트와 제 포트를 알아야 하므로 그 둘을 여기서 읽는다(run_mcp.ps1 과 같은 규칙).
$envFile = Join-Path $AppPath 'backend\.env'
function Read-EnvValue([string]$name, [string]$default) {
    if (-not (Test-Path $envFile)) { return $default }
    $line = Select-String -Path $envFile -Pattern ("^\s*" + $name + "\s*=\s*(.+)$") | Select-Object -First 1
    if (-not $line) { return $default }
    return $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
}

function Escape-Xml([string]$text) { return [System.Security.SecurityElement]::Escape($text) }

<#
서비스 하나의 정의. 이름은 서비스 id 이자 실행 파일 이름이다(WinSW 는 제 이름의 xml 을 찾는다).

  <onfailure>        죽으면 10초 뒤, 또 죽으면 30초 뒤 되살린다. 세 번째부터는 1분.
                     DB 가 아직 안 올라온 부팅 직후에 특히 이것이 일한다.
  <resetfailure>     한 시간 잘 돌았으면 실패 횟수를 0 으로.
  <delayedAutoStart> 부팅 직후 PostgreSQL 보다 먼저 뜨려다 실패하는 것을 줄인다.
  <stoptimeout>      uvicorn 이 요청을 마무리할 시간. 넘기면 죽인다.
  <log>              래퍼가 받은 stdout/stderr — 10MB 씩 8개까지 돌려 쓴다.
#>
function New-ServiceXml {
    param(
        [string]$Id, [string]$DisplayName, [string]$Description,
        [string]$Executable, [string]$Arguments, [string]$WorkingDirectory,
        [hashtable]$Env, [string[]]$DependsOn
    )
    $lines = @(
        '<service>',
        "  <id>$(Escape-Xml $Id)</id>",
        "  <name>$(Escape-Xml $DisplayName)</name>",
        "  <description>$(Escape-Xml $Description)</description>",
        "  <executable>$(Escape-Xml $Executable)</executable>",
        "  <arguments>$(Escape-Xml $Arguments)</arguments>",
        "  <workingdirectory>$(Escape-Xml $WorkingDirectory)</workingdirectory>"
    )
    foreach ($key in ($Env.Keys | Sort-Object)) {
        $lines += "  <env name=""$(Escape-Xml $key)"" value=""$(Escape-Xml $Env[$key])"" />"
    }
    foreach ($dep in $DependsOn) { $lines += "  <depend>$(Escape-Xml $dep)</depend>" }
    $lines += @(
        "  <logpath>$(Escape-Xml $logDir)</logpath>",
        '  <log mode="roll-by-size">',
        '    <sizeThreshold>10240</sizeThreshold>',
        '    <keepFiles>8</keepFiles>',
        '  </log>',
        '  <onfailure action="restart" delay="10 sec" />',
        '  <onfailure action="restart" delay="30 sec" />',
        '  <onfailure action="restart" delay="1 min" />',
        '  <resetfailure>1 hour</resetfailure>',
        '  <startmode>Automatic</startmode>',
        '  <delayedAutoStart>true</delayedAutoStart>',
        '  <stoptimeout>30 sec</stoptimeout>',
        '</service>'
    )
    return ($lines -join "`r`n") + "`r`n"
}

function Get-Definitions {
    $backendPort = Read-EnvValue 'PORT' '8020'
    $defs = @(
        @{
            Id = 'TestScope'
            DisplayName = 'TestScope'
            Description = "TestScope 시험 장비 지도 — API 와 화면 (포트 $backendPort). 앱 폴더 $AppPath"
            Executable = Join-Path $venvs 'backend\Scripts\python.exe'
            Arguments = 'run.py'
            WorkingDirectory = Join-Path $AppPath 'backend'
            Env = @{ PYTHONIOENCODING = 'utf-8'; PYTHONUNBUFFERED = '1' }
            DependsOn = @()
        }
    )
    $hasMcp = Test-Path (Join-Path $AppPath 'mcp_server\server.py')
    if ($hasMcp -and -not $NoMcp) {
        $mcpPort = Read-EnvValue 'MCP_PORT' '8022'
        $mcpHost = Read-EnvValue 'MCP_HOST' '127.0.0.1'
        $defs += @{
            Id = 'TestScope-MCP'
            DisplayName = 'TestScope MCP'
            Description = "TestScope AI 연결(MCP) — 포트 $mcpPort. 백엔드 서비스 뒤에 뜬다"
            Executable = Join-Path $venvs 'mcp_server\Scripts\python.exe'
            Arguments = '-c "import server; server.mcp.run(transport=''http'')"'
            WorkingDirectory = Join-Path $AppPath 'mcp_server'
            Env = @{
                PYTHONIOENCODING = 'utf-8'
                PYTHONUNBUFFERED = '1'
                TESTSCOPE_API_BASE = "http://127.0.0.1:$backendPort/api"
                FASTMCP_PORT = "$mcpPort"
                FASTMCP_HOST = "$mcpHost"
            }
            # 백엔드가 먼저다. 없으면 MCP 의 도구가 전부 「연결할 수 없다」 로 실패한다.
            DependsOn = @('TestScope')
        }
    }
    return $defs
}

function Get-ServiceOrNull([string]$id) {
    return Get-Service -Name $id -ErrorAction SilentlyContinue
}

function Invoke-WinSW([string]$id, [string]$command) {
    $exe = Join-Path $serviceDir "$id.exe"
    Invoke-Native "서비스 $id $command 실패" { & $exe $command }
}

function Install-One($def) {
    $id = $def.Id
    if (-not (Test-Path $def.Executable)) {
        throw "서비스 $id 가 띄울 인터프리터가 없습니다: $($def.Executable) — deploy.ps1(venv_sync.ps1)이 먼저 만들어야 합니다."
    }
    $exe = Join-Path $serviceDir "$id.exe"
    $xml = Join-Path $serviceDir "$id.xml"

    $existing = Get-ServiceOrNull $id
    if ($existing -and $existing.Status -ne 'Stopped') {
        Write-Log "서비스 $id 중지 (정의를 갱신하기 위해)"
        Stop-Service -Name $id -Force -ErrorAction Stop
        (Get-Service -Name $id).WaitForStatus('Stopped', (New-TimeSpan -Seconds 60))
    }

    # 실행 파일은 멈춘 뒤에만 바꿀 수 있다 — 윈도우는 도는 exe 를 잠근다.
    # 패키지의 WinSW 가 바뀌었을 때(판 올림)만 복사한다.
    $same = (Test-Path $exe) -and
        ((Get-FileHash $exe -Algorithm SHA256).Hash -eq (Get-FileHash $winsw -Algorithm SHA256).Hash)
    if (-not $same) { Copy-Item -Force $winsw $exe }

    $content = New-ServiceXml -Id $id -DisplayName $def.DisplayName -Description $def.Description `
        -Executable $def.Executable -Arguments $def.Arguments -WorkingDirectory $def.WorkingDirectory `
        -Env $def.Env -DependsOn $def.DependsOn
    [System.IO.File]::WriteAllText($xml, $content, (New-Object System.Text.UTF8Encoding $false))

    if ($existing) {
        # WinSW 2.x 에는 정의만 갱신하는 명령이 없다 — 지우고 다시 만든다. 지운 직후 SCM 이
        # 「삭제 표시」 상태로 잠시 붙잡고 있어 곧바로 만들면 실패하므로, 실제로 사라질 때까지
        # 기다린다(서비스 관리자 창이 열려 있으면 안 사라진다 — 닫아야 한다).
        Write-Log "서비스 $id 재등록 (정의 갱신)"
        Invoke-WinSW $id 'uninstall'
        $deadline = (Get-Date).AddSeconds(60)
        while ((Get-ServiceOrNull $id) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
        if (Get-ServiceOrNull $id) {
            throw "서비스 $id 가 아직 지워지지 않았습니다(삭제 표시 상태). 서비스 관리자(services.msc) 창을 닫고 다시 실행하세요."
        }
    } else {
        Write-Log "서비스 $id 등록"
    }
    Invoke-WinSW $id 'install'
    Write-Log "서비스 $id 시작"
    Invoke-WinSW $id 'start'
}

function Uninstall-One([string]$id) {
    $existing = Get-ServiceOrNull $id
    if (-not $existing) { Write-Log "서비스 $id 는 등록돼 있지 않습니다"; return }
    if ($existing.Status -ne 'Stopped') {
        Write-Log "서비스 $id 중지"
        Stop-Service -Name $id -Force -ErrorAction Stop
        (Get-Service -Name $id).WaitForStatus('Stopped', (New-TimeSpan -Seconds 60))
    }
    Write-Log "서비스 $id 제거"
    Invoke-WinSW $id 'uninstall'
}

function Show-Status {
    foreach ($id in @('TestScope', 'TestScope-MCP')) {
        $svc = Get-ServiceOrNull $id
        if ($svc) {
            Write-Host ("  {0,-14} {1,-10} {2}" -f $id, $svc.Status, $svc.StartType)
        } else {
            Write-Host ("  {0,-14} {1}" -f $id, '등록 안 됨')
        }
    }
    Write-Host "  로그: $logDir"
}

switch ($Action) {
    'install' {
        if (-not (Test-Path $winsw)) {
            throw "패키지에 WinSW 가 없습니다: $winsw — 이 릴리스는 서비스 등록을 지원하지 않습니다(v0.5.0 이전). 콘솔로 띄우거나 새 릴리스를 배포하세요."
        }
        New-Item -ItemType Directory -Force -Path $serviceDir, $logDir | Out-Null
        foreach ($def in Get-Definitions) { Install-One $def }
        # MCP 를 빼기로 했는데 전에 등록돼 있으면 내린다 — 없는 것으로 알고 있는 서비스가 돌면 안 된다.
        if ($NoMcp) { Uninstall-One 'TestScope-MCP' }
        Write-Host ''
        Show-Status
    }
    'uninstall' {
        # MCP 가 백엔드에 의존하므로 MCP 부터 내린다.
        foreach ($id in @('TestScope-MCP', 'TestScope')) { Uninstall-One $id }
    }
    'start' {
        foreach ($id in @('TestScope', 'TestScope-MCP')) {
            if (Get-ServiceOrNull $id) { Write-Log "서비스 $id 시작"; Start-Service -Name $id -ErrorAction Stop }
        }
        Show-Status
    }
    'stop' {
        foreach ($id in @('TestScope-MCP', 'TestScope')) {
            $svc = Get-ServiceOrNull $id
            if ($svc -and $svc.Status -ne 'Stopped') { Write-Log "서비스 $id 중지"; Stop-Service -Name $id -Force -ErrorAction Stop }
        }
        Show-Status
    }
    'restart' {
        foreach ($id in @('TestScope-MCP', 'TestScope')) {
            $svc = Get-ServiceOrNull $id
            if ($svc -and $svc.Status -ne 'Stopped') { Stop-Service -Name $id -Force -ErrorAction Stop }
        }
        foreach ($id in @('TestScope', 'TestScope-MCP')) {
            if (Get-ServiceOrNull $id) { Write-Log "서비스 $id 시작"; Start-Service -Name $id -ErrorAction Stop }
        }
        Show-Status
    }
    'status' { Show-Status }
}
