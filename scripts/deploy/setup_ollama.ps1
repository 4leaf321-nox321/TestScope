<#
임베딩 엔진 설치 — **명령 하나로 설치·서비스 등록·모델 내려받기까지.**

의미 검색이 쓰는 Ollama 를 윈도우 서버에 올린다. 한 번만 돌린다 — 배포(`deploy.ps1`)는
이것을 **설치하지 않고 살아 있는지만 본다**. 배포가 매번 1.2GB 를 받게 하면 배포가 몇 분씩
길어지고, 인터넷이 잠깐 막힌 날 배포가 실패한다.

## 이미 도는 Ollama 가 있으면 그것을 쓴다

같은 서버에 다른 앱(MatNexus 등)이 올린 Ollama 가 11434 에서 응답하면 **서비스를 또 등록하지
않는다** — 두 작업이 같은 포트를 두고 다투면 뒤에 뜬 쪽이 조용히 죽는다. 모델만 확인하고
받는다. 그래서 이 스크립트는 「내 것」 이 아니라 「이 PC 의 임베딩 엔진」 을 준비하는 것이다.

## 왜 작업 스케줄러인가

Ollama 의 윈도우 설치본은 **로그인한 사람의 트레이 앱**으로 뜬다. 서버는 아무도
로그인해 있지 않으므로 그대로 두면 재부팅 뒤에 조용히 안 돈다 — 그리고 그 사실은
「의미 검색이 안 되네」 로만 드러난다.

그래서 `ollama serve` 를 **SYSTEM 계정으로 시작 시 실행**되는 작업으로 등록한다.
NSSM 같은 외부 서비스 래퍼를 안 쓰는 이유는 하나 더 받아야 할 것이 생기기 때문이고,
`Register-ScheduledTask -User SYSTEM` 은 윈도우에 원래 있다.

## 모델 자리를 못 박는다

SYSTEM 으로 돌면 모델이 `C:\Windows\System32\config\systemprofile\.ollama` 에 들어간다.
사람이 `ollama pull` 을 손으로 돌리면 그건 **자기 프로필**에 받는다 — 둘이 갈리면
「분명히 받았는데 서비스는 없다고 한다」 가 된다. `OLLAMA_MODELS` 를 기계 전역
변수로 박아 양쪽이 같은 자리를 보게 한다.

사용:
  .\setup_ollama.ps1                          # 설치 + 서비스 + bge-m3
  .\setup_ollama.ps1 -Model bge-m3 -Port 11434
  .\setup_ollama.ps1 -SkipService             # 서비스 없이 지금 세션에서만
  .\setup_ollama.ps1 -CheckOnly               # 아무것도 안 바꾸고 상태만 본다
#>

param(
    [string]$Model = 'bge-m3',
    [int]$Port = 11434,
    [string]$ModelPath = 'C:\ProgramData\Ollama\models',
    [string]$TaskName = 'TestScope-Ollama',
    [switch]$SkipService,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$installer = 'https://ollama.com/download/OllamaSetup.exe'
$base = "http://127.0.0.1:$Port"

function Write-Log([string]$m) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $m" }

# 5.1 은 네이티브 명령이 stderr 에 한 줄만 내도 종료성 오류로 바꾼다. 종료 코드로 본다.
function Invoke-Native {
    param([Parameter(Mandatory = $true)][string]$FailureMessage, [Parameter(Mandatory = $true)][scriptblock]$Command)
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

function Get-OllamaExe {
    $found = Get-Command ollama -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    # 설치본은 사용자 프로필에 깔린다. PATH 는 새 셸부터 반영되므로 직접 본다.
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe"
    )
    foreach ($one in $candidates) { if (Test-Path $one) { return $one } }
    return $null
}

function Test-Alive {
    try {
        $answer = Invoke-WebRequest -UseBasicParsing "$base/api/tags" -TimeoutSec 3
        return $answer.StatusCode -eq 200
    } catch { return $false }
}

function Wait-Alive([int]$Seconds = 60) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Alive) { return $true }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

# --- 지금 상태 ---------------------------------------------------------------
$exe = Get-OllamaExe
Write-Log ("실행 파일: " + $(if ($exe) { $exe } else { '없음' }))
Write-Log ("응답($base): " + $(if (Test-Alive) { '살아 있음' } else { '없음' }))

if ($CheckOnly) {
    # **응답이 곧 준비다.** 실행 파일이 우리가 아는 자리에 없어도(다른 앱이 다른 곳에 깔았거나
    # 컨테이너로 돈다) 11434 가 답하고 모델이 있으면 앱은 쓸 수 있다.
    if (-not (Test-Alive)) {
        if (-not $exe) { Write-Log '설치되지 않았습니다. 인자 없이 다시 돌리면 설치합니다.' }
        else { Write-Log '설치는 됐는데 응답이 없습니다 — 서비스가 안 도는 상태입니다.' }
        exit 1
    }
    $tags = (Invoke-WebRequest -UseBasicParsing "$base/api/tags").Content | ConvertFrom-Json
    $names = @($tags.models | ForEach-Object { $_.name })
    Write-Log ("모델 " + $names.Count + "개: " + ($names -join ', '))
    if (-not ($names | Where-Object { $_ -like "$Model*" })) {
        Write-Log "'$Model' 이 없습니다."; exit 1
    }
    Write-Log '준비됐습니다.'
    exit 0
}

# --- 1. 설치 -----------------------------------------------------------------
# 이미 응답하면 설치하지 않는다 — 실행 파일이 우리가 아는 자리에 없더라도(2 를 보라).
if ((-not $exe) -and (Test-Alive)) {
    Write-Log '실행 파일은 못 찾았지만 엔진이 응답합니다 — 설치를 건너뜁니다.'
} elseif (-not $exe) {
    Write-Log 'Ollama 를 설치합니다.'
    # winget 이 있으면 그쪽이 낫다 — 나중에 올릴 때도 같은 길이다. 윈도우 서버
    # 이미지에는 없는 일이 흔해서, 없으면 설치본을 직접 받는다.
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Invoke-Native 'winget 설치 실패' {
            & winget install --id Ollama.Ollama -e --silent --accept-source-agreements --accept-package-agreements
        }
    } else {
        $temp = Join-Path $env:TEMP 'OllamaSetup.exe'
        Write-Log "설치본을 받습니다: $installer"
        # 진행 표시줄을 끄면 대용량 다운로드가 몇 배 빨라진다(5.1 의 알려진 함정).
        $previousProgress = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        try {
            Invoke-WebRequest -UseBasicParsing $installer -OutFile $temp
        } finally {
            $ProgressPreference = $previousProgress
        }
        Write-Log '조용히 설치합니다 (Inno Setup).'
        $run = Start-Process -FilePath $temp -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru
        if ($run.ExitCode -ne 0) { throw "설치본이 실패했습니다 (exit $($run.ExitCode))" }
    }
    $exe = Get-OllamaExe
    if (-not $exe) { throw '설치는 끝났는데 ollama.exe 를 못 찾았습니다. 로그인 세션을 새로 열고 다시 돌려 보세요.' }
    Write-Log "설치 완료: $exe"
} else {
    Write-Log '이미 설치돼 있습니다.'
}

# --- 2. 모델 자리 ------------------------------------------------------------
# **기계 전역이어야 한다.** SYSTEM 으로 도는 서비스와 사람이 손으로 돌리는
# `ollama pull` 이 같은 자리를 봐야 「받았는데 없다」 가 안 생긴다. 이미 전역 값이
# 있으면(다른 앱이 정했으면) 그대로 둔다 — 바꾸면 그쪽 모델이 안 보이게 된다.
$already = [Environment]::GetEnvironmentVariable('OLLAMA_MODELS', 'Machine')
if ($already) {
    $ModelPath = $already
    Write-Log "모델 자리(이미 정해짐): $ModelPath"
} else {
    if (-not (Test-Path $ModelPath)) { New-Item -ItemType Directory -Force $ModelPath | Out-Null }
    [Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $ModelPath, 'Machine')
    Write-Log "모델 자리: $ModelPath"
}
$env:OLLAMA_MODELS = $ModelPath

# --- 3. 서비스(작업 스케줄러) ------------------------------------------------
if (Test-Alive) {
    # 누가 띄웠든 이미 도는 것을 쓴다. 우리 작업이 없어도 등록하지 않는다 — 재부팅 뒤에
    # 그쪽이 안 뜨면 그때 이 스크립트를 다시 돌리면 된다(그때는 응답이 없으니 등록한다).
    $ours = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Log ("엔진이 이미 응답합니다 — 서비스를 " + $(if ($ours) { "다시 등록하지 않습니다('$TaskName' 있음)." } else { '등록하지 않습니다(다른 앱이 띄운 것을 씁니다).' }))
} elseif ($SkipService) {
    Write-Log '서비스 등록을 건너뜁니다.'
    if (-not (Test-Alive)) {
        Write-Log '이 세션에서만 띄웁니다 — 재부팅하면 사라집니다.'
        Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden
    }
} else {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Log "'$TaskName' 작업이 이미 있습니다 — 새로 씁니다."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    $action = New-ScheduledTaskAction -Execute $exe -Argument 'serve'
    $trigger = New-ScheduledTaskTrigger -AtStartup
    # SYSTEM 은 비밀번호가 필요 없다 — 사람 계정으로 등록하면 비밀번호를 어딘가
    # 적어 두게 되고, 그 계정의 비밀번호가 바뀌는 날 조용히 멈춘다.
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings `
        -Description 'TestScope 의미 검색이 쓰는 임베딩 엔진(Ollama).' | Out-Null
    Write-Log "'$TaskName' 등록 완료 — 시작 시 SYSTEM 으로 돕니다."

    if (-not (Test-Alive)) {
        Start-ScheduledTask -TaskName $TaskName
        Write-Log '지금 띄웁니다.'
    }
}

if (-not (Wait-Alive 90)) {
    throw "$base 가 90초 안에 응답하지 않았습니다. 작업 스케줄러에서 '$TaskName' 의 마지막 실행 결과를 보세요."
}
Write-Log '엔진이 응답합니다.'

# --- 4. 모델 -----------------------------------------------------------------
$tags = (Invoke-WebRequest -UseBasicParsing "$base/api/tags").Content | ConvertFrom-Json
$have = @($tags.models | ForEach-Object { $_.name }) | Where-Object { $_ -like "$Model*" }
if ($have) {
    Write-Log "모델이 이미 있습니다: $($have -join ', ')"
} else {
    Write-Log "'$Model' 을 받습니다 — 1GB 안팎이라 몇 분 걸립니다."
    if ($exe) {
        Invoke-Native "모델 내려받기 실패: $Model" { & $exe pull $Model }
    } else {
        # 실행 파일이 없어도 엔진의 API 로 받을 수 있다.
        $pull = @{ name = $Model; stream = $false } | ConvertTo-Json
        $answer = Invoke-WebRequest -UseBasicParsing "$base/api/pull" -Method Post -Body $pull -ContentType 'application/json' -TimeoutSec 3600
        if (($answer.Content | ConvertFrom-Json).status -ne 'success') { throw "모델 내려받기 실패: $Model — $($answer.Content)" }
    }
    Write-Log '모델 준비 완료.'
}

# --- 5. 진짜로 되는지 --------------------------------------------------------
# **살아 있다는 것과 임베딩이 나온다는 것은 다르다.** 여기서 한 번 재 보고
# 차원을 찍는다 — 그 숫자가 백엔드 설정(EMBEDDING_DIM)과 맞아야 한다.
Write-Log '임베딩을 한 번 재 봅니다.'
$body = @{ model = $Model; input = '80도에서 20 kN 인장 시험이 되는 장비' } | ConvertTo-Json
$started = Get-Date
$answer = Invoke-WebRequest -UseBasicParsing "$base/api/embed" -Method Post -Body $body -ContentType 'application/json'
$took = [int]((Get-Date) - $started).TotalMilliseconds
$vector = ($answer.Content | ConvertFrom-Json).embeddings[0]
if (-not $vector) { throw '임베딩이 비어서 돌아왔습니다.' }

Write-Host ''
Write-Log "차원 $($vector.Count) · $took ms"
Write-Log '백엔드 .env 에 이렇게 적고 워커 서비스를 다시 띄웁니다(service.ps1 -Action restart):'
Write-Host ''
Write-Host "    EMBEDDING_BACKEND=ollama"
Write-Host "    OLLAMA_BASE_URL=$base"
Write-Host "    EMBEDDING_MODEL=$Model"
Write-Host "    EMBEDDING_DIM=$($vector.Count)"
Write-Host ''
