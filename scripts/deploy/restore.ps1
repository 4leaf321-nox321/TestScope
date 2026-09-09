<#
백업에서 되돌린다.

**기본은 확인용 복구다.** 다른 이름의 DB 로 덤프를 풀어 "이 백업이 실제로 살아
있는가" 를 본다 — 받아만 두고 복구를 해 본 적이 없는 백업은 백업이 아니다.
운영 DB 를 덮어쓰려면 `-Force` 를 의식적으로 준다.

    .\restore.ps1 -BackupRoot 'D:\TestAtlas-backup' -DbName testatlas_restore_check
    .\restore.ps1 -BackupRoot 'D:\TestAtlas-backup' -DbName testatlas -AppPath 'C:\Server\TestAtlas' -Force

**파일스토어는 -AppPath 를 줄 때만 되돌린다.** DB 만 확인하는 경우에 운영 파일을
건드리면 그 자체가 사고다.
#>

param(
    [Parameter(Mandatory = $true)][string]$BackupRoot,
    [Parameter(Mandatory = $true)][string]$DbName,
    [string]$AppPath,
    [string]$DumpFile,
    [switch]$Force,
    [string]$PgRestoreExe,
    [string]$PsqlExe
)

$ErrorActionPreference = 'Stop'
function Write-Log([string]$m) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $m" }

function Invoke-Native([string]$exe, [string[]]$arguments, [string]$what, [int[]]$okCodes = @(0)) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $exe @arguments
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($okCodes -notcontains $code) { throw "$what 실패 (exit $code)" }
    return $code
}

# --- 접속 정보 ----------------------------------------------------------------
# 백업이 함께 받아 둔 .env 에서 읽는다. 앱이 살아 있지 않아도 복구할 수 있어야
# 한다 — 서버가 통째로 날아간 상황이 바로 복구가 필요한 상황이다.
$envFile = Join-Path $BackupRoot 'env\.env'
if (-not (Test-Path $envFile)) { throw "백업에 .env 가 없습니다: $envFile" }
$dsn = ((Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -match '^DATABASE_URL=' }) -replace '^DATABASE_URL=', '').Trim()
if ($dsn -notmatch '://(?<user>[^:]+):(?<pw>[^@]*)@(?<host>[^:/]+):(?<port>\d+)/(?<db>.+)$') {
    throw 'DATABASE_URL 을 해석하지 못했습니다.'
}
$dbUser = $Matches['user']; $dbPw = $Matches['pw']
$dbHost = $Matches['host']; $dbPort = $Matches['port']; $sourceDb = $Matches['db']

if ($DbName -eq $sourceDb -and -not $Force) {
    throw @"
'$DbName' 은 운영 데이터베이스입니다. 확인만 하려면 다른 이름을 주세요:

  .\restore.ps1 -BackupRoot '$BackupRoot' -DbName ${sourceDb}_restore_check

정말 운영을 덮어쓰려면 -Force 를 주세요. **되돌릴 수 없습니다.**
"@
}

# --- 덤프 고르기 --------------------------------------------------------------
if (-not $DumpFile) {
    $latest = Get-ChildItem (Join-Path $BackupRoot 'db') -Filter 'db-*.dump' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) { throw "백업에 덤프가 없습니다: $(Join-Path $BackupRoot 'db')" }
    $DumpFile = $latest.FullName
}
if (-not (Test-Path $DumpFile)) { throw "덤프를 찾을 수 없습니다: $DumpFile" }
$dumpMb = [math]::Round((Get-Item $DumpFile).Length / 1MB, 1)
Write-Log "덤프: $DumpFile (${dumpMb}MB)"

# --- 도구 찾기 ----------------------------------------------------------------
foreach ($pair in @(@('PgRestoreExe', 'pg_restore.exe'), @('PsqlExe', 'psql.exe'))) {
    $name = $pair[0]; $exe = $pair[1]
    if (-not (Get-Variable $name -ValueOnly)) {
        $found = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\$exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) { Set-Variable $name $found.FullName }
        elseif (Get-Command ($exe -replace '\.exe$', '') -ErrorAction SilentlyContinue) {
            Set-Variable $name ($exe -replace '\.exe$', '')
        } else { throw "$exe 를 찾지 못했습니다. -$name 로 경로를 지정하세요." }
    }
}

$env:PGPASSWORD = $dbPw
try {
    # --- 대상 DB 준비 ---------------------------------------------------------
    # **비어 있는 DB 로 복구한다.** 기존 표 위에 덮으면 덤프에 없는 옛 행이 남아,
    # 복구했는데도 데이터가 섞인 상태가 된다.
    Write-Log "대상 데이터베이스 준비: $DbName"
    $exists = & $PsqlExe -U $dbUser -h $dbHost -p $dbPort -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" postgres
    if ($exists -eq '1') {
        if (-not $Force) {
            throw "'$DbName' 이 이미 있습니다. 지우고 다시 만들려면 -Force 를 주세요."
        }
        Write-Log "기존 $DbName 삭제"
        Invoke-Native $PsqlExe @('-U', $dbUser, '-h', $dbHost, '-p', $dbPort, '-c',
            "DROP DATABASE `"$DbName`"", 'postgres') 'DROP DATABASE' | Out-Null
    }
    Invoke-Native $PsqlExe @('-U', $dbUser, '-h', $dbHost, '-p', $dbPort, '-c',
        "CREATE DATABASE `"$DbName`" ENCODING 'UTF8'", 'postgres') 'CREATE DATABASE' | Out-Null

    # --- 복구 -----------------------------------------------------------------
    # pg_restore 는 경고를 stderr 로 내고 종료 코드 1 을 쓸 수 있다(확장 소유권 등).
    # 그것으로 복구 전체를 실패로 보지 않는다 — 아래 표 개수로 판정한다.
    Write-Log '복구 중'
    Invoke-Native $PgRestoreExe @('--host', $dbHost, '--port', $dbPort, '--username', $dbUser,
        '--dbname', $DbName, '--no-owner', '--no-privileges', $DumpFile) 'pg_restore' @(0, 1) | Out-Null

    $tables = & $PsqlExe -U $dbUser -h $dbHost -p $dbPort -tAc `
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" $DbName
    Write-Log "복구된 표: $($tables.Trim()) 개"
    if ([int]$tables.Trim() -eq 0) { throw '표가 하나도 복구되지 않았습니다. 덤프를 확인하세요.' }
} finally {
    $env:PGPASSWORD = ''
}

# --- 파일스토어 ---------------------------------------------------------------
if ($AppPath) {
    $storeSource = Join-Path $BackupRoot 'filestore'
    $storeTarget = Join-Path ($AppPath + '_data') 'filestore'
    if (Test-Path $storeSource) {
        Write-Log "파일스토어 복구: $storeSource -> $storeTarget"
        New-Item -ItemType Directory -Force -Path $storeTarget | Out-Null
        Invoke-Native 'robocopy.exe' @($storeSource, $storeTarget, '/MIR', '/R:2', '/W:5', '/NFL', '/NDL', '/NJH', '/NP') `
            'robocopy' @(0, 1, 2, 3, 4, 5, 6, 7) | Out-Null
    } else {
        Write-Warning "백업에 파일스토어가 없습니다 ($storeSource)."
    }
} else {
    Write-Log '파일스토어는 건드리지 않았습니다 (-AppPath 를 주지 않음).'
}

Write-Host ''
Write-Host '복구 완료.'
if ($DbName -ne $sourceDb) {
    Write-Host ''
    Write-Host "  확인용 DB 입니다: $DbName"
    Write-Host '  다 봤으면 지우세요:'
    Write-Host "    psql -U $dbUser -h $dbHost -c 'DROP DATABASE `"$DbName`"' postgres"
}
Write-Host ''

<#
**성공했으면 0 으로 끝난다.**

PowerShell 스크립트의 종료 코드는 마지막 네이티브 명령의 $LASTEXITCODE 를 그대로
물려받는다. robocopy 는 **성공했을 때도 0 이 아닌 값**을 낸다(비트 플래그 — 1 은
"파일을 복사했다" 는 뜻이다). 그대로 두면 백업이 멀쩡히 끝났는데도 스크립트가
1 로 끝나고, **작업 스케줄러는 그것을 매일 실패로 기록한다** — 그러면 사람은
곧 그 알림을 무시하게 되고, 진짜 실패한 날에도 아무도 안 본다.

실측: 이 스크립트를 처음 돌렸을 때 덤프·미러·기록이 다 남았는데 exit=1 이었다.
#>
exit 0
