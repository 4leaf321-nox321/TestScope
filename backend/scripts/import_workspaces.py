"""ReportArchive 의 부서 정보 CSV 를 들인다 — 명령줄.

화면의 「관리 → 부서 정보 → 가져오기」 와 **같은 코드**(`app/modules/workspaces/imports.py`)를
쓴다. 규칙(무엇을 안 옮기나 · 멱등 · slug 를 안 고침)은 그 모듈 머리에 있다.

    python scripts/import_workspaces.py 부서정보.csv --dry-run
    python scripts/import_workspaces.py 부서정보.csv
    python scripts/import_workspaces.py 부서정보.csv --update     # 있는 부서를 덮는다
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.workspaces import imports

survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="ReportArchive 부서 정보를 들인다")
    parser.add_argument("path", type=Path, help="부서정보.csv")
    parser.add_argument(
        "--update",
        action="store_true",
        help="이미 있는 부서의 이름·설명·순서·보관 상태를 저쪽 값으로 덮는다",
    )
    parser.add_argument("--dry-run", action="store_true", help="무엇이 들어갈지만 본다")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"파일이 없습니다: {args.path}")
        return 1
    # BOM 을 벗긴다 — 저쪽이 Excel 을 위해 붙인다. 안 벗기면 첫 컬럼 이름이 깨진다.
    rows = imports.parse(args.path.read_text(encoding="utf-8-sig"))

    db = SessionLocal()
    try:
        # 만든 사람이 그 부서의 관리자로 들어간다. 반입은 시스템 관리자의 이름으로 한다.
        actor = db.scalar(select(User).where(User.is_system_admin.is_(True)))
        if actor is None:
            raise SystemExit(
                "시스템 관리자가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요."
            )

        if args.dry_run:
            planned = imports.plan(db, rows, update_existing=args.update)
            print("(dry-run — 아무것도 안 바꿨습니다)")
        else:
            planned = imports.apply(db, rows, creator=actor, update_existing=args.update)
            db.commit()

        made = sum(1 for one in planned if one.action == "create")
        updated = sum(1 for one in planned if one.action == "update")
        skipped = [one for one in planned if one.action.startswith("skip")]
        errors = [one for one in planned if one.action == "error"]
        print(
            f"부서 {len(rows)}줄에서: 새로 {made} · 갱신 {updated} · 건너뜀 {len(skipped)}"
            f" · 오류 {len(errors)}"
        )
        for label, ones in (("건너뛴 줄", skipped), ("오류 줄", errors)):
            if not ones:
                continue
            print(f"\n{label}:")
            for one in ones[:25]:
                print(f"  {one.line:4d}행 {one.slug:32s} {one.reason}")
            if len(ones) > 25:
                print(f"  … 외 {len(ones) - 25}줄")
        if any((row.get("external_view_default") or "").strip() for row in rows):
            print(
                "\n공개 정책(external_view_default)은 안 옮겼습니다 — 저쪽은 보고서 공개이고"
                " 이쪽은 장비 가시성이라 다른 물음입니다. 필요하면 부서 정보 화면에서"
                " 「멤버만」 을 직접 켜세요."
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
