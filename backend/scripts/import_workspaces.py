"""ReportArchive 의 부서 정보 CSV 를 들인다.

ReportArchive 화면의 「부서 정보 내보내기」(`/api/workspaces/export.csv`)가 내는 파일을
그대로 받는다. 컬럼:

    slug · name · parent_slug · parent_name · depth · path · kind · status
    description · sort_order · external_view_default · member_count · managers · created_at

    python scripts/import_workspaces.py 부서정보.csv --dry-run
    python scripts/import_workspaces.py 부서정보.csv

## 무엇을 안 옮기나 — 이게 이 스크립트의 요점이다

**`external_view_default` 는 안 옮긴다.** 저쪽에서는 「이 게시판의 보고서를 다른
조직이 볼 수 있나」 이고, 이쪽 `restricted` 는 「이 부서의 장비를 멤버에게만 보이나」 다.
글자만 비슷하지 **다른 물음에 답하는 칸**이다. 게다가 기본값이 서로 반대라, 그대로
뒤집어 넣으면 반입 직후 **모든 부서의 장비가 검색에서 사라진다.**

`depth` · `path` · `parent_name` 은 파생값이라 안 읽는다 — 우리도 트리에서 다시
만든다. `member_count` · `managers` 는 저쪽 계정 이야기라 안 옮긴다.

## 멱등하다

슬러그가 열쇠다. 이미 있는 부서는 **안 덮는다** — 여기서 고쳐 둔 이름을 저쪽 판이
되돌리면 그것은 사고다. 갱신하려면 `--update` 를 준다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import func, select

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.accounts.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.shared.text import clean

survive_cp949()

#: 반드시 있어야 하는 컬럼. 나머지는 없으면 없는 대로 둔다.
REQUIRED = ("slug", "name")

#: 기본으로 들이는 종류.
#:
#: **org 만이다.** 저쪽 `virtual` 은 자식을 묶어 보여 주는 집계 노드고 `tf` 는
#: 조직도 밖의 한시 조직인데, 이쪽 부서는 **장비의 소유자이자 권한의 단위**다 —
#: 장비를 소유하지 않는 노드를 부서로 만들면 목록에 빈 줄이 늘고, 그 줄은 아무도
#: 안 지운다. 필요하면 `--kinds` 로 넓힌다.
#:
#: 저쪽 export 는 `personal` 을 이미 빼고 낸다(사용자마다 생기는 개인 공간).
DEFAULT_KINDS = ("org",)

#: 슬러그 길이 상한. 표와 같아야 한다 — 넘으면 자르지 않고 거절한다.
SLUG_MAX = 64


def _read(path: Path) -> list[dict[str, str]]:
    """CSV 를 읽는다. **BOM 을 벗긴다** — 저쪽이 Excel 을 위해 붙인다.

    안 벗기면 첫 컬럼 이름이 `\ufeffslug` 가 되어, 슬러그가 통째로 비어 보인다.
    """
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        raise SystemExit("빈 파일입니다.")
    missing = [name for name in REQUIRED if name not in rows[0]]
    if missing:
        raise SystemExit(
            f"필요한 칸이 없습니다: {', '.join(missing)}. "
            f"ReportArchive 의 「부서 정보 내보내기」 파일이 맞는지 확인하세요."
        )
    return rows


def _ordered(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """부모가 먼저 오게 놓는다.

    저쪽 export 는 이미 깊이우선 순서지만 **그것에 기대지 않는다** — 사람이 엑셀에서
    정렬을 한 번 누르면 그 순서는 사라지고, 그때 자식이 먼저 와서 부모를 못 찾는다.
    """

    def depth(row: dict[str, str]) -> int:
        try:
            return int(row.get("depth") or 0)
        except ValueError:
            return 0

    return sorted(rows, key=depth)


def _flag(value: str | None) -> bool | None:
    if value is None or value.strip() == "":
        return None
    return value.strip().lower() in ("true", "1", "y", "yes")


def _number(value: str | None, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def main() -> int:
    parser = argparse.ArgumentParser(description="ReportArchive 부서 정보를 들인다")
    parser.add_argument("path", type=Path, help="부서정보.csv")
    parser.add_argument(
        "--kinds",
        default=",".join(DEFAULT_KINDS),
        help="들일 종류 (org,tf,virtual). 기본은 org 만",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="이미 있는 부서의 이름·설명·순서를 저쪽 값으로 덮는다",
    )
    parser.add_argument("--dry-run", action="store_true", help="무엇이 들어갈지만 본다")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"파일이 없습니다: {args.path}")
        return 1
    kinds = {one.strip() for one in args.kinds.split(",") if one.strip()}
    rows = _ordered(_read(args.path))

    db = SessionLocal()
    try:
        # 만든 사람이 그 부서의 관리자로 들어간다 — 아니면 방금 만든 부서에 아무도
        # 손댈 수 없다. 반입은 시스템 관리자의 이름으로 한다.
        actor = db.scalar(select(User).where(User.is_system_admin.is_(True)))
        if actor is None:
            raise SystemExit(
                "시스템 관리자가 없습니다. 먼저 scripts/seed_install.py 를 돌리세요."
            )

        known = {row.slug: row for row in db.scalars(select(Workspace))}
        made = updated = 0
        skipped: list[tuple[str, str]] = []

        for row in rows:
            slug = clean(row.get("slug") or "")
            name = clean(row.get("name") or "")
            kind = (row.get("kind") or "org").strip() or "org"

            if not slug or not name:
                skipped.append((slug or "(빈 슬러그)", "슬러그나 이름이 비었습니다"))
                continue
            if kind not in kinds:
                skipped.append((slug, f"{kind} 종류는 안 들입니다"))
                continue
            if len(slug) > SLUG_MAX:
                # **자르지 않는다.** 자르면 키가 달라져서 다음 반입 때 같은 부서가
                # 하나 더 생긴다.
                skipped.append((slug, f"슬러그가 {SLUG_MAX}자를 넘습니다"))
                continue

            parent_slug = clean(row.get("parent_slug") or "") or None
            parent = known.get(parent_slug) if parent_slug else None
            if parent_slug and parent is None:
                skipped.append((slug, f"상위 부서를 못 찾았습니다: {parent_slug}"))
                continue

            found = known.get(slug)
            if found is not None:
                if not args.update:
                    continue
                found.name = name
                found.description = clean(row.get("description") or "")[:255]
                found.sort_order = _number(row.get("sort_order"), found.sort_order)
                if (row.get("status") or "").strip():
                    found.is_active = (row["status"] or "").strip() != "archived"
                updated += 1
                continue

            last = db.scalar(
                select(func.max(Workspace.sort_order)).where(
                    Workspace.parent_id == (parent.id if parent else None)
                )
            )
            workspace = Workspace(
                slug=slug,
                name=name,
                description=clean(row.get("description") or "")[:255],
                parent_id=parent.id if parent else None,
                sort_order=_number(row.get("sort_order"), (last or 0) + 1),
                # archived 는 보관 상태다 — 자료는 남기고 새 활동만 막는다.
                is_active=(row.get("status") or "active").strip() != "archived",
                # **`external_view_default` 를 여기 넣지 않는다.** 다른 물음에
                # 답하는 칸이고, 기본값이 서로 반대라 뒤집어 넣으면 반입 직후
                # 모든 부서의 장비가 검색에서 사라진다.
            )
            db.add(workspace)
            db.flush()
            db.add(
                WorkspaceMember(workspace_id=workspace.id, user_id=actor.id, role="manager")
            )
            known[slug] = workspace
            made += 1

        if args.dry_run:
            db.rollback()
            print("(dry-run — 되돌렸습니다)")
        else:
            db.commit()

        print(f"부서 {len(rows)}줄에서: 새로 {made} · 갱신 {updated} · 건너뜀 {len(skipped)}")
        if skipped:
            print("\n건너뛴 줄:")
            for slug, why in skipped[:25]:
                print(f"  {slug:32s} {why}")
            if len(skipped) > 25:
                print(f"  … 외 {len(skipped) - 25}줄")
        if any((row.get("external_view_default") or "").strip() for row in rows):
            print(
                "\n공개 정책(external_view_default)은 안 옮겼습니다 — 저쪽은 보고서"
                " 공개이고 이쪽은 장비 가시성이라 다른 물음입니다. 필요하면 부서"
                " 관리 화면에서 「멤버에게만」 을 직접 켜세요."
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
