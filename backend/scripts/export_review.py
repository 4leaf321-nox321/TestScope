"""검토함의 결정을 정본(`source/catalog/proposals/<queue>.json`)에 되돌려 쓴다.

    python scripts/export_review.py            # 네 큐 전부
    python scripts/export_review.py --check    # 무엇이 바뀔지만 본다

## 왜 되돌려 쓰나

도메인 전문가가 화면에서 고른 것은 이 설치의 DB 에만 있다. 정본에 `decided` 로 적어 두면
운영 서버가 반입할 때(`import_catalog.py` → `review.refresh`) **적용까지 되고 다시 묻지
않는다.** 물성 연결의 `export_property_links.py` 와 같은 길이다 — 개발에서 확인한 것을 정본에
싣고, 정본이 운영으로 간다.

## 정본의 줄이 없는 결정

파생 후보(규격의 시험 항목)는 정본에 줄이 없어도 선다. 그런 결정은 새 줄로 더한다 — 후보
없이 `subject` 와 `decided` 만 갖는 줄이고, 다음 refresh 가 후보를 다시 파생한다.

## 사람이 고친 추천은 안 건드린다

이 스크립트는 `decided` 만 쓴다. `recommended` · `reason` · `hint` 는 사람이 정본에 적는 것.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.review import services

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="검토함의 결정을 정본에 되돌려 쓴다")
    parser.add_argument("--root", type=Path, default=services.PROPOSALS_DIR)
    parser.add_argument("--check", action="store_true", help="무엇이 바뀔지만 보고 안 쓴다")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        for queue, (decided, written, added) in services.export_decisions(
            db, args.root, write=not args.check
        ).items():
            label = services.QUEUES[queue].label
            print(f"{label}: 결정 {decided}건 → 정본에 적음 {written} (새 줄 {added})")
        if args.check:
            print("(--check 였습니다 — 아무것도 쓰지 않았습니다)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
