"""부서 정보를 ReportArchive 와 **같은 형식**으로 내보낸다.

컬럼과 순서를 저쪽 `/api/workspaces/export.csv` 에 맞춘다. 그래야 왕복이 된다 —
한쪽으로만 들어가는 것은 호환이 아니라 이사다.

**행을 만드는 것은 서비스가 한다**(`workspaces.services.export_rows`). 화면의
내려받기 버튼도 같은 함수를 쓴다 — 두 벌이면 반드시 갈리고, 갈린 날 두 파일이
다르게 나온다.

    python scripts/export_workspaces.py                 부서정보.csv 로
    python scripts/export_workspaces.py -o 어디에.csv

## 우리가 모르는 칸

`kind` 는 전부 `org` 다 — 이쪽에는 집계 노드도 한시 조직도 없다.
`external_view_default` 는 **비운다.** 이쪽 `restricted` 는 장비 가시성이라 저쪽의
보고서 공개 정책과 다른 물음이고, 아는 척해서 채우면 그 값이 저쪽에서 정책이 된다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.workspaces.services import EXPORT_HEADER, export_rows

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="부서 정보를 CSV 로 내보낸다")
    parser.add_argument("-o", "--out", type=Path, default=Path("부서정보.csv"))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = export_rows(db)
        # **BOM 을 붙인다.** 안 붙이면 Excel 이 한글을 깬다 — 저쪽과 같은 규약이다.
        with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(EXPORT_HEADER)
            writer.writerows(rows)
        print(f"부서 {len(rows)}개를 {args.out} 에 썼습니다.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
