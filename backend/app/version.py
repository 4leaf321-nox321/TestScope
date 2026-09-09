"""이 설치가 어느 버전인가.

버전을 물을 자리가 없으면, 문제가 났을 때 "지금 서버에 뭐가 깔렸나" 를 답할 수
없다. 값은 배포 패키지가 들고 온다(BUILD_INFO.txt 의 version=) — 깔린 파일
자신이 자기 버전을 알아야 기록과 실제 코드가 어긋나지 않는다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

#: 어디서도 못 찾았을 때. 개발 중이거나 패키지가 아닌 경로에서 돈다는 뜻이다.
UNKNOWN = "unknown"

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _from_build_info() -> str | None:
    path = BACKEND_DIR.parent / "BUILD_INFO.txt"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1].strip() or None
    return None


def _from_package_json() -> str | None:
    """개발 중에는 저장소의 frontend/package.json 이 정본이다."""
    path = BACKEND_DIR.parent / "frontend" / "package.json"
    if not path.exists():
        return None
    try:
        return "v" + str(json.loads(path.read_text(encoding="utf-8"))["version"])
    except (ValueError, KeyError):
        return None


@lru_cache(maxsize=1)
def current() -> str:
    return _from_build_info() or _from_package_json() or UNKNOWN


#: 계약 baseline 파일에 박는 값. **실제 버전을 넣지 않는다** — openapi.json 은
#: 프론트 타입의 입력이라, 버전을 실으면 버전을 올릴 때마다 기준 파일이 어긋난다.
BASELINE = "baseline"


def as_baseline(schema: dict[str, Any]) -> dict[str, Any]:
    info = {**schema.get("info", {}), "version": BASELINE}
    return {**schema, "info": info}
