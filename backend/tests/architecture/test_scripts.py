"""배포 스크립트가 지켜야 하는 것.

지침 문서에만 적힌 규칙은 반드시 어긋난다 — 급할 때 사람은 문서를 안 읽는다.
여기서 검사하는 것만이 실제로 지켜지는 규칙이다.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"

BOM = b"\xef\xbb\xbf"

#: 훑지 않을 곳. 남의 패키지가 들고 온 .ps1 까지 우리 규칙으로 재지 않는다.
_SKIP = {"node_modules", ".venv", ".git"}


def _repo_scripts() -> list[Path]:
    """**저장소 전체**의 .ps1.

    `scripts/` 만 보면 루트의 activate.ps1 이 빠진다 — 실제로 그렇게 빠져 있었다.

    패키징 산출물(루트의 `deploy/`)은 뺀다 — **루트의 그것만**. 전에는 경로 어디든 `deploy`
    가 있으면 뺐고, 그러면 `scripts/deploy/*.ps1` 이 통째로 검사에서 빠진다. 실제로 그래서
    배포 스크립트의 BOM 도, $command 충돌도 여기서 못 잡았다.
    """
    made: list[Path] = []
    for path in REPO.rglob("*.ps1"):
        parts = path.relative_to(REPO).parts
        if _SKIP & set(parts) or parts[0] in ("deploy", "deploy_cache"):
            continue
        made.append(path)
    return made


def test_ps1_은_utf8_bom_으로_저장한다() -> None:
    """**Windows PowerShell 5.1 이 BOM 없는 스크립트를 CP949 로 읽는다.**

    그러면 주석과 오류 메시지의 한글이 깨지고, 운이 나쁘면 구문 오류가 난다 —
    배포하려는 순간에 배포 스크립트가 안 도는 것이 가장 나쁘다.

    편집 도구가 BOM 을 떼는 일이 흔하므로 시험이 지킨다.
    """
    missing = [
        str(path.relative_to(REPO))
        for path in _repo_scripts()
        if not path.read_bytes().startswith(BOM)
    ]
    assert not missing, "UTF-8 BOM 이 없습니다: " + ", ".join(missing)


def test_네이티브_명령은_종료_코드로_판정한다() -> None:
    """5.1 은 네이티브 명령이 stderr 에 한 줄만 써도 종료성 오류로 바꾼다.

    **alembic 은 INFO 로그를 stderr 로 낸다** — 감싸지 않으면 정상 배포가 실패로
    뒤집힌다. alembic·pg_dump·robocopy 를 부르는 스크립트는 감싸는 함수를 갖는다.
    """
    for name in ("deploy.ps1", "install.ps1", "backup.ps1", "restore.ps1", "service.ps1"):
        text = (SCRIPTS / "deploy" / name).read_text(encoding="utf-8-sig")
        assert "function Invoke-Native" in text, f"{name} 에 Invoke-Native 가 없습니다"


def test_Invoke_Native_블록_안에서_command_변수를_안_쓴다() -> None:
    """Invoke-Native 의 매개변수가 `$Command`(블록 자신)다. 호출부가 같은 이름을 블록 안에
    쓰면 동적 스코프 때문에 **블록 자신**으로 풀리고, PowerShell 은 그것을 exe 에
    `-encodedCommand` 로 넘긴다 — 운영 첫 설치에서 WinSW 가 「Unknown command」 로 전부 죽었다.
    `$FailureMessage` 도 같은 이유로 막는다."""
    import re

    for path in _repo_scripts():
        text = path.read_text(encoding="utf-8-sig")
        if "function Invoke-Native" not in text:
            continue
        # 정의 자체는 빼고 본다.
        start = text.index("function Invoke-Native")
        end = text.index("\n}\n", start) + 3
        outside = text[:start] + text[end:]
        clashes = re.findall(r"\$(?:command|failuremessage)\b", outside, flags=re.IGNORECASE)
        assert not clashes, (
            f"{path.name}: Invoke-Native 밖에서 $Command/$FailureMessage 를 씁니다 — "
            "블록 안에서 블록 자신으로 풀립니다. 다른 이름을 쓰세요."
        )


def test_대시_두_개를_막는다() -> None:
    """`--AppPath '<경로>'` 로 쓰면 PowerShell 은 오류를 내지 않는다.

    그 글자 자체가 첫 위치 매개변수에 들어가고 **진짜 값은 다음 매개변수로 밀려
    들어간다** — deploy.ps1 에서는 그것이 -Repo 라서 저장소 이름 자리에 경로가
    가고, 사람은 "gh 가 안 된다" 를 보게 된다.
    """
    for name in ("deploy.ps1", "install.ps1", "rollback.ps1", "backup.ps1", "service.ps1"):
        text = (SCRIPTS / "deploy" / name).read_text(encoding="utf-8-sig")
        assert "Assert-NotFlag" in text, f"{name} 에 Assert-NotFlag 가 없습니다"


def test_패키지에_배포_스크립트가_다_들어간다() -> None:
    """서버가 릴리스만 받는 환경이어도 zip 하나로 그다음 배포가 돌아야 한다.

    빠뜨리면 첫 배포에 저장소를 클론하는 수밖에 없고, 폐쇄망에서는 그 길이 없다.
    """
    packaged = (SCRIPTS / "ci" / "package_deploy.ps1").read_text(encoding="utf-8-sig")
    for path in (SCRIPTS / "deploy").glob("*.ps1"):
        assert path.name in packaged, f"package_deploy.ps1 이 {path.name} 을 안 담습니다"


def test_패키지에_카탈로그_원천이_든다() -> None:
    """계열·기종·물성은 데이터라 마이그레이션으로 안 간다. 서버의 import_catalog.py 가
    <AppPath>\\source\\catalog 를 읽는데, 패키지에 없으면 폐쇄망에서는 들일 길이 없다 —
    실제로 그래서 운영 카탈로그가 비어 있었다."""
    packaged = (SCRIPTS / "ci" / "package_deploy.ps1").read_text(encoding="utf-8-sig")
    # proposals: 검토함 정본(후보·추천·결정). 빠지면 운영 검토함이 한 물음만 선다.
    for part in ("equipment", "ontology", "proposals", "schema.json", "sources.json"):
        assert f"'{part}'" in packaged, (
            f"package_deploy.ps1 이 source\\catalog\\{part} 를 안 담습니다"
        )
    assert "materialtwin" in packaged, (
        "package_deploy.ps1 이 source\\materialtwin 을 안 담습니다"
    )


def test_서비스_래퍼는_판과_해시를_못_박고_설치가_등록한다() -> None:
    """부팅 때 뜨는 것은 Windows 서비스(WinSW)가 해 준다. 그 exe 는 저장소가 아니라
    패키징이 받아 담는데, **판과 sha256 을 못 박지 않으면** 어느 날 다른 바이너리가
    폐쇄망 서버로 들어간다. 그리고 담기만 하고 install.ps1 이 안 부르면 재부팅한 날
    아침에 화면이 안 열린다."""
    packaged = (SCRIPTS / "ci" / "package_deploy.ps1").read_text(encoding="utf-8-sig")
    assert "$winswVersion = 'v" in packaged, (
        "package_deploy.ps1 이 WinSW 판을 못 박지 않습니다"
    )
    assert "Get-FileHash" in packaged and "$winswSha256" in packaged, (
        "package_deploy.ps1 이 WinSW 의 sha256 을 검사하지 않습니다"
    )
    assert "WinSW-x64.exe" in packaged, "package_deploy.ps1 이 WinSW 를 담지 않습니다"
    install = (SCRIPTS / "deploy" / "install.ps1").read_text(encoding="utf-8-sig")
    assert "service.ps1" in install, "install.ps1 이 service.ps1 을 안 부릅니다"
    # 배포와 롤백은 서비스를 스스로 멈추고 올린다 — 사람이 잊으면 잠금에 막힌다.
    for name in ("deploy.ps1", "rollback.ps1"):
        text = (SCRIPTS / "deploy" / name).read_text(encoding="utf-8-sig")
        assert "Stop-Service" in text and "Start-AppServices" in text, (
            f"{name} 이 서비스를 멈추고 올리지 않습니다"
        )


def test_설치가_부르는_시드_스크립트가_있다() -> None:
    """스크립트 이름을 고치면 배포가 조용히 그 단계를 잃는다 — 그때 화면은 빈
    목록을 보여 주고, 사람은 그것을 "값이 없다" 로 읽는다."""
    backend_scripts = REPO / "backend" / "scripts"
    for name, caller in (
        ("seed_install.py", "install.ps1"),
        ("seed_reference.py", "deploy.ps1"),
        ("ensure_semantic_schema.py", "deploy.ps1"),
    ):
        assert (backend_scripts / name).exists(), f"{name} 이 없습니다"
        text = (SCRIPTS / "deploy" / caller).read_text(encoding="utf-8-sig")
        assert name in text, f"{caller} 이 {name} 을 안 부릅니다"


def test_콘솔이_아닌_출력에서_죽지_않게_한다() -> None:
    """**다 끝난 작업이 traceback 으로 끝나면 사람은 그것을 실패로 읽는다.**

    한글은 CP949 로 나가지만 줄표 같은 글자는 못 나간다. 콘솔에 직접 찍을 때는
    콘솔 API 를 타서 멀쩡한데, deploy.ps1 이 출력을 받아 가는 순간 locale 로
    떨어져 그때만 터진다 — 사람이 손으로 돌릴 때는 안 보이는 자리다.
    """
    for path in (REPO / "backend" / "scripts").glob("*.py"):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "survive_cp949()" in text, f"{path.name} 이 survive_cp949 를 안 부릅니다"


def test_배포는_중단된_교체를_이어받고_폴더_이동은_되돌릴_수_있다() -> None:
    """운영 폴더는 없고 _prev 만 남은 상태(지난 배포가 새 버전 배치에서 멈춤)를 첫 배포로
    읽으면 .env 를 이어받지 않아 마이그레이션이 DATABASE_URL 없이 실패한다 — 실제로 그렇게
    깨졌다. 그리고 새 버전 배치의 이름 바꾸기는 백신이 새 파일을 훑는 몇 초 동안 「액세스
    거부」 로 튀므로 다시 시도하고, 끝내 안 되면 현재 설치를 제자리로 돌린다."""
    text = (SCRIPTS / "deploy" / "deploy.ps1").read_text(encoding="utf-8-sig")
    assert "$isResume" in text and "-or $isResume" in text, (
        "deploy.ps1 이 _prev 만 남은 중단 상태에서 .env 를 이어받지 않습니다"
    )
    assert "Move-FolderWithRetry" in text, "deploy.ps1 이 폴더 이동을 다시 시도하지 않습니다"
    assert "Directory]::Move($prevPath, $AppPath)" in text, (
        "deploy.ps1 이 새 버전 배치 실패 때 현재 설치를 되돌리지 않습니다"
    )
