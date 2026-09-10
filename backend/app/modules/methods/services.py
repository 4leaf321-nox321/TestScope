"""시험법 로직."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.capabilities.models import Capability
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.methods.schemas import MethodOut, RequirementOut
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.pagination import Page
from app.shared.permissions import (
    require_owner_edit,
    resolve_owner_workspace,
    visible_owner_clause,
)
from app.shared.text import clean

_WHAT = "시험법"
_CODE = "TSC-METHODS-0002"


def visible(db: Session, user: User) -> Select[tuple[TestMethod]]:
    """전역 시험법 + 내 부서 시험법. 목록·상세·검색이 **같은 것**을 봐야 한다."""
    return select(TestMethod).where(
        TestMethod.deleted_at.is_(None),
        visible_owner_clause(user, TestMethod.owner_workspace_id),
    )


def get_method(db: Session, user: User, method_id: uuid.UUID) -> TestMethod:
    found = db.scalar(visible(db, user).where(TestMethod.id == method_id))
    if found is None:
        raise NotFound("TSC-METHODS-0001", "시험법을 찾을 수 없습니다.")
    return found


def _requirements(db: Session, method_id: uuid.UUID) -> list[RequirementOut]:
    rows = db.execute(
        select(MethodRequirement, ConditionKey)
        .join(ConditionKey, ConditionKey.id == MethodRequirement.condition_key_id)
        .where(MethodRequirement.method_id == method_id)
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all()
    return [
        RequirementOut(
            id=req.id,
            condition_key_id=key.id,
            condition_key=key.key,
            condition_label=key.label,
            si_unit=key.si_unit,
            display_unit=key.display_unit,
            min_value=req.min_value,
            max_value=req.max_value,
            text_value=req.text_value,
            is_mandatory=req.is_mandatory,
            note=req.note,
        )
        for req, key in rows
    ]


def _can_edit(db: Session, user: User, row: TestMethod) -> bool:
    try:
        require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    except AppError:
        return False
    return True


def method_out(db: Session, row: TestMethod, viewer: User) -> MethodOut:
    item = db.get(VocabularyTerm, row.test_item_term_id) if row.test_item_term_id else None
    body = db.get(VocabularyTerm, row.body_term_id) if row.body_term_id else None
    workspace = db.get(Workspace, row.owner_workspace_id) if row.owner_workspace_id else None
    successor = db.get(TestMethod, row.superseded_by_id) if row.superseded_by_id else None
    equipment_count = (
        db.scalar(
            select(func.count(func.distinct(Capability.equipment_id))).where(
                Capability.method_id == row.id
            )
        )
        or 0
    )
    return MethodOut(
        id=row.id,
        code=row.code,
        edition=row.edition,
        title=row.title,
        test_item=item.value if item else None,
        test_item_term_id=row.test_item_term_id,
        body=body.value if body else None,
        status=row.status,
        superseded_by_code=successor.code if successor else None,
        summary=row.summary,
        workspace_slug=workspace.slug if workspace else None,
        equipment_count=equipment_count,
        requirements=_requirements(db, row.id),
        created_at=row.created_at,
        can_edit=_can_edit(db, viewer, row),
    )


def list_methods(
    db: Session,
    user: User,
    *,
    query: str | None,
    test_item_term_id: uuid.UUID | None,
    include_superseded: bool,
    limit: int,
    offset: int,
) -> Page[MethodOut]:
    stmt = visible(db, user)
    if query:
        text = f"%{clean(query)}%"
        stmt = stmt.where(TestMethod.code.ilike(text) | TestMethod.title.ilike(text))
    if test_item_term_id:
        stmt = stmt.where(TestMethod.test_item_term_id == test_item_term_id)
    if not include_superseded:
        # **기본은 현행만.** 대체된 판이 섞여 있으면 사람이 옛 규격을 고르고,
        # 그 사실은 시험이 끝난 뒤에야 드러난다.
        stmt = stmt.where(TestMethod.status != "superseded")

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(TestMethod.code, TestMethod.edition).limit(limit).offset(offset)
    )
    return Page(
        items=[method_out(db, row, user) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def create(db: Session, user: User, payload: dict[str, Any]) -> TestMethod:
    code = clean(payload["code"])
    edition = clean(payload.get("edition") or "") or None
    clash = db.scalar(
        select(TestMethod).where(
            TestMethod.code == code,
            TestMethod.edition.is_(edition)
            if edition is None
            else TestMethod.edition == edition,
            TestMethod.deleted_at.is_(None),
        )
    )
    if clash is not None:
        raise Conflict("TSC-METHODS-0003", f"이미 등록된 규격입니다: {code} {edition or ''}")

    owner = resolve_owner_workspace(
        db, user, payload.get("workspace_slug"), what=_WHAT, code=_CODE
    )
    row = TestMethod(
        code=code,
        edition=edition,
        title=clean(payload["title"]),
        test_item_term_id=payload.get("test_item_term_id"),
        body_term_id=payload.get("body_term_id"),
        summary=payload.get("summary"),
        owner_workspace_id=owner,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


_PLAIN_FIELDS = ("title", "edition", "test_item_term_id", "body_term_id", "summary")


def update(
    db: Session, user: User, method_id: uuid.UUID, changes: dict[str, Any]
) -> TestMethod:
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)

    for field in _PLAIN_FIELDS:
        if field in changes:
            setattr(row, field, changes[field])

    if changes.get("status") == "superseded" and row.status != "superseded":
        # **대체는 되돌릴 수 없는 부류다.** 이 규격을 걸고 있던 역량 전부의 뜻이
        # 바뀌고, 그 사실을 반년 뒤에 물을 자리가 감사 기록밖에 없다.
        successor = (
            db.get(TestMethod, changes["superseded_by_id"])
            if changes.get("superseded_by_id")
            else None
        )
        audit.record(
            db,
            action=audit.METHOD_SUPERSEDED,
            actor=user,
            target_table="test_methods",
            target_id=row.id,
            target_label=f"{row.code} {row.edition or ''}".strip(),
            workspace_id=row.owner_workspace_id,
            changes={
                "superseded_by": {
                    "before": None,
                    "after": successor.code if successor else None,
                }
            },
        )
    if "status" in changes and changes["status"] is not None:
        row.status = changes["status"]
    if "superseded_by_id" in changes:
        row.superseded_by_id = changes["superseded_by_id"]

    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, method_id: uuid.UUID) -> None:
    """소프트 삭제.

    **대체된 규격은 지우는 것이 아니다** — 옛 판으로 잰 데이터가 있고, 그것이
    어느 판이었는지는 남아야 한다. 삭제는 잘못 등록한 행을 위한 것이다.
    """
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    using = (
        db.scalar(
            select(func.count()).select_from(Capability).where(Capability.method_id == row.id)
        )
        or 0
    )
    if using:
        raise Conflict(
            "TSC-METHODS-0004",
            f"이 시험법을 거는 역량이 {using}건 있습니다. "
            f"지우는 대신 상태를 대체됨으로 바꾸세요.",
        )
    row.deleted_at = datetime.now(UTC)
    db.commit()


def upsert_requirement(
    db: Session, user: User, method_id: uuid.UUID, payload: dict[str, Any]
) -> RequirementOut:
    """요구 조건 하나를 넣거나 덮어쓴다.

    같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없으므로 **덮어쓰기가 기본**이다.
    """
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)

    key = db.get(ConditionKey, payload["condition_key_id"])
    if key is None:
        raise NotFound("TSC-METHODS-0005", "조건 정의를 찾을 수 없습니다.")

    existing = db.scalar(
        select(MethodRequirement).where(
            MethodRequirement.method_id == row.id,
            MethodRequirement.condition_key_id == key.id,
        )
    )
    target = existing or MethodRequirement(method_id=row.id, condition_key_id=key.id)
    target.min_value = payload.get("min_value")
    target.max_value = payload.get("max_value")
    target.text_value = payload.get("text_value")
    target.is_mandatory = payload.get("is_mandatory", True)
    target.note = payload.get("note")
    if existing is None:
        db.add(target)
    db.commit()

    return next(one for one in _requirements(db, row.id) if one.condition_key_id == key.id)


def delete_requirement(
    db: Session, user: User, method_id: uuid.UUID, requirement_id: uuid.UUID
) -> None:
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    target = db.get(MethodRequirement, requirement_id)
    if target is None or target.method_id != row.id:
        raise NotFound("TSC-METHODS-0006", "요구 조건을 찾을 수 없습니다.")
    db.delete(target)
    db.commit()
