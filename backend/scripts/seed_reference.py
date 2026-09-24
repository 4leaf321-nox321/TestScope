"""온톨로지 축과 조건 정의만 심는다 — **배포가 매번 부른다.**

`seed_install.py` 와 나눈 이유: 설치 시드는 관리자 계정과 뿌리 부서까지 만드는데,
그것은 **첫 설치에서 한 번**만 할 일이다. 배포가 그것을 부르면 계정 생성 경로가
릴리스마다 다시 돌게 된다.

축은 행이라 `alembic upgrade` 로는 안 들어간다. 새 축을 더한 릴리스를 배포하고
나면 그 축을 쓰는 화면이 빈 목록을 보여 주고, 사람은 그것을 "값이 없다" 로 읽는다.

    python scripts/seed_reference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.vocabulary.reference import ensure_reference_data

survive_cp949()


def main() -> int:
    db = SessionLocal()
    try:
        counts = ensure_reference_data(db)
        if any(counts):
            print(
                f"온톨로지: 축 {counts.axes}개, 조건 정의 {counts.conditions}개, "
                f"사양 그룹 {counts.spec_groups}개, 사양 정의 {counts.spec_definitions}개 추가"
                f" · 검색축 이음 {counts.linked_definitions}개"
                f", 문장→구간 {counts.converted_values}건"
                f", 보유 장비 속성 {counts.attributes}개"
            )
        else:
            print("온톨로지: 이미 갖춰져 있습니다")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
