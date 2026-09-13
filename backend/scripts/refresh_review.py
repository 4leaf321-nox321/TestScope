"""검토함의 후보를 다시 세운다 — 정본(`source/catalog/proposals/*.json`)이 바뀐 뒤.

    python scripts/refresh_review.py

화면의 「다시 세우기」(시스템 관리자) 와 같은 일이다. 반입(`import_catalog.py`)도 끝에 이것을
하므로, 반입 없이 정본만 고쳤을 때 쓴다 — 예: `catalog_extension/tools_propose.py` 를 다시
돌린 뒤.
정한 것은 안 건드린다 — 후보와 근거만 따라 바뀐다.
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
    parser = argparse.ArgumentParser(description="검토함의 후보를 다시 세운다")
    parser.add_argument("--root", type=Path, default=services.PROPOSALS_DIR)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        counts = services.refresh(db, args.root)
        db.commit()
        for queue, open_count in counts.items():
            print(f"{services.QUEUES[queue].label}: 열림 {open_count}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
