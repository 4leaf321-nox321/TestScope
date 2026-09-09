"""OpenAPI 스키마를 파일로 뽑는다 — **프론트 타입의 원본이다.**

    python scripts/export_openapi.py
    cd ../frontend && npm run api:types

손으로 적은 프론트 타입은 반드시 서버와 어긋난다. 어긋난 날 화면은 아무 말도
안 하고 undefined 를 그린다.

버전 도장은 지운다(version.as_baseline). 안 지우면 버전을 올릴 때마다 이 파일이
바뀌어, "API 가 바뀌었나" 를 이 파일의 diff 로 볼 수 없게 된다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _console import survive_cp949
from app import version
from app.main import app

survive_cp949()

OUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> int:
    schema = version.as_baseline(app.openapi())
    OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT} 에 썼습니다 ({len(schema.get('paths', {}))} 경로).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
