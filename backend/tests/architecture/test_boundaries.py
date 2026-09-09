"""구조 규칙을 시험이 지킨다.

지침 문서에만 적힌 규칙은 반드시 어긋난다 — 급할 때 사람은 문서를 안 읽는다.
여기서 검사하는 것만이 실제로 지켜지는 규칙이다.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
MODULES = BACKEND / "app" / "modules"

#: 모듈 이름이 프론트와 같아야 한다는 규칙의 예외. **사유와 함께** 적는다.
#:   capabilities — 프론트에서는 장비 상세의 한 패널이라 equipment 안에 산다.
#:   resolve      — 화면이 아니라 **도구가 쓰는 모듈**이다. AI·MCP 가 「이게 이미
#:                  있나」 를 묻는 자리고, 사람은 그 물음을 피커 안에서 한다
#:                  (equipment/ModelPicker). 짝을 만들면 빈 폴더가 하나 는다.
#:   search       — 프론트 모듈 이름이 같다(예외 아님, 여기 적지 않는다).
FRONTEND_MERGED = {"capabilities", "resolve"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_모듈끼리_라우터를_직접_부르지_않는다() -> None:
    """조립 지점은 main.py 하나다.

    모듈이 서로의 routes 를 import 하면 조립 순서가 여러 곳에 흩어지고, 그때
    "이 엔드포인트가 왜 안 뜨지" 를 물을 자리가 없어진다.
    """
    offenders: list[str] = []
    for path in MODULES.rglob("*.py"):
        module = path.relative_to(MODULES).parts[0]
        for name in _imports(path):
            if not name.startswith("app.modules."):
                continue
            other = name.split(".")[2]
            if other != module and name.endswith(".routes"):
                offenders.append(f"{path.relative_to(BACKEND)} -> {name}")
    assert not offenders, "모듈이 남의 라우터를 직접 부릅니다: " + ", ".join(offenders)


def test_shared_는_도메인_라우터를_모른다() -> None:
    """방향은 shared -> 모듈 한 쪽이다.

    shared 가 라우터를 알면 순환이 생기고, 그때 import 순서 하나로 서버가 안 뜬다.
    모델과 서비스는 부를 수 있다(권한 판정이 그것을 필요로 한다).
    """
    for path in (BACKEND / "app" / "shared").rglob("*.py"):
        for name in _imports(path):
            assert not name.endswith(".routes"), f"{path.name} 이 {name} 을 부릅니다"


def test_모든_모델이_all_models_에_있다() -> None:
    """빠뜨리면 autogenerate 가 **기존 표를 지우는** 마이그레이션을 만든다.

    앱에서는 안 드러나고, 배포 뒤 마이그레이션을 돌릴 때만 터진다.
    """
    registered = (BACKEND / "app" / "all_models.py").read_text(encoding="utf-8")
    for path in MODULES.rglob("models.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            # Base 를 상속한 것만 ORM 모델이다.
            if any(isinstance(base, ast.Name) and base.id == "Base" for base in node.bases):
                assert node.name in registered, (
                    f"{node.name} 이 all_models.py 에 없습니다 ({path.relative_to(BACKEND)})"
                )


def test_오류_코드_접두사가_하나다() -> None:
    """MNX 같은 다른 프로젝트의 접두사가 섞이면 로그 검색이 반만 걸린다."""
    for path in (BACKEND / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "MNX-" not in text, f"{path.relative_to(BACKEND)} 에 다른 접두사가 있습니다"


def test_모듈_이름이_백엔드와_프론트에서_같다() -> None:
    """이름이 갈리면 **어느 화면이 어느 API 를 쓰는지** 추적이 사람의 기억에 걸린다.

    예외는 위 FRONTEND_MERGED 에 사유와 함께 적는다 — 목록에 있다는 것 자체가
    "여기는 일부러 다르다" 는 기록이다.
    """
    frontend = BACKEND.parent / "frontend" / "src" / "modules"
    if not frontend.exists():  # pragma: no cover - 백엔드만 받은 설치
        return

    backend_modules = {
        path.name
        for path in MODULES.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    frontend_modules = {path.name for path in frontend.iterdir() if path.is_dir()}

    only_backend = backend_modules - frontend_modules - FRONTEND_MERGED
    assert not only_backend, f"프론트에 짝이 없는 모듈: {sorted(only_backend)}"
