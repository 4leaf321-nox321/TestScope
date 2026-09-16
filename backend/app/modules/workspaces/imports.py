"""ReportArchive 부서 정보 가져오기 — **조직도를 두 번 치지 않는다.**

ReportArchive 의 「부서 정보 내보내기」(`/api/workspaces/export.csv`)가 낸 파일을 그대로
받는다. 두 시스템을 같은 조직이 쓰는데 부서를 양쪽에 손으로 치면, 오타 하나로 「같은 부서가
다른 이름」 이 된다 — slug 가 갈리는 순간 사람이 눈으로 못 잡는다.

## 형식

    slug · name · parent_slug · parent_name · depth · path · kind · status
    description · sort_order · external_view_default · member_count · managers · created_at

쉼표(내보내기 파일)든 탭(엑셀에서 복사)이든 받는다 — 첫 줄을 보고 정한다. 머리글이 있어야
한다. 쓰는 것은 **slug · name · parent_slug · kind · status · description · sort_order** 다.

## 무엇을 안 옮기나 — 이게 요점이다

**`external_view_default` 는 안 옮긴다.** 저쪽은 「이 게시판의 보고서를 다른 조직이 볼 수
있나」 이고 이쪽 `restricted` 는 「이 부서의 장비를 멤버에게만 보이나」 다. 글자만 비슷하지
**다른 물음에 답하는 칸**이고, 기본값이 서로 반대라 뒤집어 넣으면 반입 직후 모든 부서의 장비가
검색에서 사라진다. `depth`·`path`·`parent_name` 은 파생값, `member_count`·`managers` 는 저쪽
계정 이야기라 안 읽는다.

## 무엇을 들이나

    org      들인다 — 조직도의 부서다
    virtual  들인다(org 로) — 저쪽 트리의 묶음 노드인데 이쪽 트리에도 같은 자리가 필요하다
    tf       건너뛴다 — 한시 조직이라 조직도가 아니다
    personal 건너뛴다 — 내보내기에도 없지만 손으로 만든 파일을 대비해 막는다

## 멱등이다 · 덮지 않는다

slug 가 열쇠다. 이미 있는 부서는 **건너뛴다** — 여기서 고친 이름을 저쪽 판이 조용히 되돌리면
고친 사람은 영문을 모른다. 덮으려면 `update_existing` 을 켠다(이름·설명·순서·보관 상태만).

## slug 를 고쳐 쓰지 않는다

규칙에 안 맞는 slug 는 오류로 낸다. 자르거나 바꿔 만들면 두 시스템이 같은 부서를 다른 주소로
부르게 된다 — 이 기능이 막으려는 바로 그 일이다.

## 미리보기와 적용은 같은 코드다

`plan()` 이 판정하고 `apply()` 가 그 계획대로 만든다. 따로면 「미리보기엔 된다더니」 가 된다.
적용은 **커밋하지 않는다** — 라우트가 한 트랜잭션으로 한다(절반만 들어간 조직도는 없느니만
못하다). CLI(`scripts/import_workspaces.py`)도 이 모듈을 쓴다.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.modules.workspaces.schemas import SLUG_PATTERN
from app.shared.errors import AppError
from app.shared.text import clean

#: 없으면 이 파일이 아니다. 값 열(멤버수 등)은 없어도 된다 — 손으로 줄인 파일을 받는다.
REQUIRED_COLUMNS = ("slug", "name")

#: 행의 운명. 화면이 이 값으로 줄 색을 정한다.
ACTIONS = ("create", "update", "skip_exists", "skip_kind", "error")

#: 들이는 종류. virtual 은 org 로.
IMPORTED_KINDS = ("org", "virtual")


@dataclass(frozen=True)
class Planned:
    """행 하나의 운명 — 만들지, 덮을지, 왜 건너뛰는지."""

    line: int
    slug: str
    name: str
    parent_slug: str | None
    action: str
    reason: str


def parse(text: str) -> list[dict[str, str]]:
    """붙여넣은 글자 → 행 dict. **형식이 아니면 무엇이 없는지 말하고 거절한다.**

    아무 글자나 받아 조용히 0건을 만들면 사람은 「가져오기가 안 된다」 만 안다.
    쉼표·탭은 첫 줄로 정한다 — 엑셀 복사는 탭, 내보내기 파일은 쉼표.
    """
    body = text.lstrip("﻿").strip()
    if not body:
        raise AppError(
            "TSC-WORKSPACES-0020", "비어 있습니다. 부서 정보 CSV 를 붙여넣으세요.", status=422
        )
    first = body.splitlines()[0]
    delimiter = "\t" if first.count("\t") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(body), delimiter=delimiter)
    header = [(name or "").strip() for name in (reader.fieldnames or [])]
    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        raise AppError(
            "TSC-WORKSPACES-0020",
            f"부서 정보 형식이 아닙니다 — {', '.join(missing)} 열이 없습니다. "
            "ReportArchive 의 「부서 정보 내보내기」 파일을 머리글까지 붙여넣으세요.",
            status=422,
        )
    return [
        {(key or "").strip(): (value or "").strip() for key, value in row.items() if key}
        for row in reader
    ]


def _depth(row: dict[str, str]) -> int:
    try:
        return int(row.get("depth") or 0)
    except ValueError:
        return 0


def _number(value: str | None, fallback: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def plan(
    db: Session, rows: list[dict[str, str]], *, update_existing: bool = False
) -> list[Planned]:
    """행마다 무엇이 일어날지. 부모가 먼저 오게 depth 로 놓는다 — 내보내기는 깊이우선이지만
    사람이 엑셀에서 정렬을 한 번 누르면 그 순서는 사라진다."""
    existing = set(db.scalars(select(Workspace.slug)))
    will_exist = set(existing)
    seen_in_file: set[str] = set()
    ordered = sorted(enumerate(rows, start=2), key=lambda pair: _depth(pair[1]))

    planned: list[Planned] = []
    for line, row in ordered:
        slug = clean(row.get("slug") or "")
        name = clean(row.get("name") or "") or slug
        parent = clean(row.get("parent_slug") or "") or None
        kind = (row.get("kind") or "org").strip() or "org"
        action, reason = _judge(
            slug,
            kind,
            parent,
            existing=existing,
            will_exist=will_exist,
            seen=seen_in_file,
            update_existing=update_existing,
        )
        planned.append(
            Planned(
                line=line,
                slug=slug,
                name=name,
                parent_slug=parent,
                action=action,
                reason=reason,
            )
        )
    return planned


def _judge(
    slug: str,
    kind: str,
    parent: str | None,
    *,
    existing: set[str],
    will_exist: set[str],
    seen: set[str],
    update_existing: bool,
) -> tuple[str, str]:
    """행 하나의 운명. `will_exist`·`seen` 을 갱신한다 — 뒤 행의 부모가 앞 행일 수 있다."""
    if not slug:
        return "error", "주소(slug)가 비어 있습니다."
    if kind not in IMPORTED_KINDS:
        if kind in ("tf", "personal"):
            return "skip_kind", "한시 조직(TF)·개인 공간은 조직도가 아니라 들이지 않습니다."
        return "skip_kind", f"모르는 종류입니다: {kind}"
    if not re.fullmatch(SLUG_PATTERN, slug):
        return "error", "주소(slug)가 규칙(소문자·숫자·하이픈, 2~50자)에 맞지 않습니다."
    if slug in seen:
        return "error", "파일 안에 같은 주소가 두 번 있습니다."
    seen.add(slug)
    if slug in existing:
        if update_existing:
            return "update", "이름·설명·순서·보관 상태를 저쪽 값으로 덮습니다."
        return "skip_exists", "이미 있는 부서라 그대로 둡니다(이름도 덮지 않습니다)."
    if parent and parent not in will_exist:
        return (
            "error",
            f"상위 부서({parent})가 여기에도, 이 파일의 앞 행에도 없습니다. "
            "TF 아래 행이거나 파일이 잘렸을 수 있습니다.",
        )
    will_exist.add(slug)
    return "create", ""


def apply(
    db: Session, rows: list[dict[str, str]], *, creator: User, update_existing: bool = False
) -> list[Planned]:
    """계획대로 만든다. **커밋하지 않는다 — 라우트가 한 번에 한다.**

    `services.create` 를 안 쓰는 이유: 그 함수는 행마다 commit 한다. 도중에 하나가 막히면
    절반만 들어간 조직도가 남고, 다시 올리면 앞 절반이 「이미 있음」 으로 갈려 무엇이 이번
    것인지 알 수 없다.
    """
    planned = plan(db, rows, update_existing=update_existing)
    by_slug = {clean(row.get("slug") or ""): row for row in rows}
    made_by_slug: dict[str, Workspace] = {}
    for one in planned:
        row = by_slug.get(one.slug, {})
        if one.action == "update":
            found = db.scalar(select(Workspace).where(Workspace.slug == one.slug))
            if found is None:
                continue
            found.name = one.name
            found.description = clean(row.get("description") or "")[:255]
            found.sort_order = _number(row.get("sort_order"), found.sort_order)
            if (row.get("status") or "").strip():
                found.is_active = (row.get("status") or "").strip() != "archived"
            continue
        if one.action != "create":
            continue
        parent: Workspace | None = None
        if one.parent_slug:
            parent = made_by_slug.get(one.parent_slug) or db.scalar(
                select(Workspace).where(Workspace.slug == one.parent_slug)
            )
        last = db.scalar(
            select(func.max(Workspace.sort_order)).where(
                Workspace.parent_id == (parent.id if parent else None)
            )
        )
        made = Workspace(
            slug=one.slug,
            name=one.name,
            description=clean(row.get("description") or "")[:255],
            parent_id=parent.id if parent else None,
            # 저쪽 트리의 형제 순서를 지킨다 — 순서는 사람이 정한 것이다.
            sort_order=_number(row.get("sort_order"), (last or 0) + 1),
            # archived 는 보관 상태다 — 자료는 남기고 새 활동만 막는다.
            is_active=(row.get("status") or "active").strip() != "archived",
            # **external_view_default 를 여기 넣지 않는다** — 모듈 머리 참조.
        )
        db.add(made)
        db.flush()
        # 만든 사람을 관리자로 — manager 0명인 부서는 태어나자마자 잠긴다.
        db.add(WorkspaceMember(workspace_id=made.id, user_id=creator.id, role="manager"))
        made_by_slug[one.slug] = made
    return planned
