"""이미 등록된 장비의 **빈 시험 조건**을 기종 사양(실측이 있으면 실측)으로 채운다.

시험 조건은 장비를 **등록할 때** 기종 사양에서 복사된다(ADR 0004). 사양 정의가 검색축에
새로 이어지면 — 2026-10-08 의 낙하 높이 · 승온·하강 속도 · 변위처럼 — 그 뒤에 등록한
장비만 그 축을 갖고, 이미 등록된 장비는 비어서 검색이 「모름」 으로 답한다.

이 스크립트는 **비어 있는 축만** 채운다. 있는 조건(사람이 적은 것 · 사양에서 온 것)은
건드리지 않는다. 규칙은 `equipment_specs.fill_missing_conditions` 한 곳에 있다.

    python scripts/fill_spec_conditions.py            # 세기만 한다(미리보기)
    python scripts/fill_spec_conditions.py --apply    # 채운다

**기본은 안 쓴다.** 무엇이 몇 건 채워질지 먼저 보고 나서 적용하게 한다.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.equipment.equipment_specs import fill_missing_conditions
from app.modules.equipment.models import Equipment
from app.modules.vocabulary.models import ConditionKey

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="등록된 장비의 빈 시험 조건 채우기")
    parser.add_argument("--apply", action="store_true", help="실제로 채운다(없으면 미리보기)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        labels = {row.id: row.label for row in db.scalars(select(ConditionKey))}
        by_axis: collections.Counter[str] = collections.Counter()
        units = 0
        for equipment in db.scalars(select(Equipment).where(Equipment.deleted_at.is_(None))):
            added = fill_missing_conditions(db, equipment)
            if added:
                units += 1
                by_axis.update(labels.get(key_id, str(key_id)) for _, key_id in added)
        total = sum(by_axis.values())
        if args.apply:
            db.commit()
        else:
            db.rollback()
        verb = "채움" if args.apply else "채울 예정(미리보기)"
        print(f"장비 {units}대 · 시험 조건 {total}건 {verb}")
        for label, count in by_axis.most_common():
            print(f"  {label}: {count}건")
        if not args.apply and total:
            print("적용하려면 --apply 를 붙여 다시 실행.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
