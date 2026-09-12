"""사양 그룹과 사양 정의 — 기종 사양표의 칸. 분류 붙이기, 검색축 잇기, 쓰이는 것은 못 지우기.

`services.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import (
    ModelSpecValue,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    VocabularyTerm,
)
from app.modules.vocabulary.schemas import (
    SpecDefinitionOut,
    SpecGroupOut,
)
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from app.modules.vocabulary.terms import (
    get_vocabulary,
)
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound

# --- 사양 정의 ---------------------------------------------------------------
#
# 조건 정의(ConditionKey)와 나란한 자리다. 조건은 검색이 묻는 일곱 축이고, 사양은
# 사양서에 적힌 수백 칸이다. 한 표로 합치면 검색 폼에 외형 치수가 뜬다(ADR 0005).


def _definition_count(db: Session, group_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(SpecDefinition)
            .where(SpecDefinition.group_id == group_id)
        )
        or 0
    )


def group_out(db: Session, row: SpecGroup) -> SpecGroupOut:
    return SpecGroupOut(
        id=row.id,
        slug=row.slug,
        label=row.label,
        description=row.description,
        sort_order=row.sort_order,
        definition_count=_definition_count(db, row.id),
    )


def list_spec_groups(db: Session) -> list[SpecGroupOut]:
    rows = db.scalars(select(SpecGroup).order_by(SpecGroup.sort_order, SpecGroup.label))
    return [group_out(db, row) for row in rows]


def get_spec_group(db: Session, group_id: uuid.UUID) -> SpecGroup:
    found = db.get(SpecGroup, group_id)
    if found is None:
        raise NotFound("TSC-SPEC-0001", "사양 그룹을 찾을 수 없습니다.")
    return found


def create_spec_group(db: Session, *, payload: dict[str, Any]) -> SpecGroup:
    if db.scalar(select(SpecGroup).where(SpecGroup.slug == payload["slug"])) is not None:
        raise Conflict("TSC-SPEC-0002", f"이미 있는 그룹 키입니다: {payload['slug']}")
    row = SpecGroup(**payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_spec_group(
    db: Session, *, group_id: uuid.UUID, changes: dict[str, Any]
) -> SpecGroup:
    row = get_spec_group(db, group_id)
    for field, value in changes.items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


def delete_spec_group(db: Session, group_id: uuid.UUID) -> None:
    """**든 사양이 있으면 거절한다.** 그룹은 사양이 매달리는 자리라 지우면 그
    사양들이 어디에 속했는지가 사라진다 — DB 도 RESTRICT 로 막지만, 그때 나오는
    말은 사람이 읽을 수 없다."""
    row = get_spec_group(db, group_id)
    using = _definition_count(db, row.id)
    if using:
        raise Conflict(
            "TSC-SPEC-0003",
            f"이 그룹에 사양이 {using}개 있습니다. 먼저 다른 그룹으로 옮기세요.",
        )
    db.delete(row)
    db.commit()


def _definition_categories(db: Session, definition_id: uuid.UUID) -> list[VocabularyTerm]:
    return list(
        db.scalars(
            select(VocabularyTerm)
            .join(
                SpecDefinitionCategory,
                SpecDefinitionCategory.category_term_id == VocabularyTerm.id,
            )
            .where(SpecDefinitionCategory.definition_id == definition_id)
            .order_by(VocabularyTerm.value)
        )
    )


def _definition_usage(db: Session, definition_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ModelSpecValue)
            .where(ModelSpecValue.definition_id == definition_id)
        )
        or 0
    )


def definition_out(db: Session, row: SpecDefinition) -> SpecDefinitionOut:
    group = db.get(SpecGroup, row.group_id)
    key = db.get(ConditionKey, row.condition_key_id) if row.condition_key_id else None
    terms = _definition_categories(db, row.id)
    return SpecDefinitionOut(
        id=row.id,
        key=row.key,
        label=row.label,
        group_id=row.group_id,
        group_slug=group.slug if group else "",
        group_label=group.label if group else "",
        kind=row.kind,
        dimension=row.dimension,
        si_unit=row.si_unit,
        display_unit=row.display_unit,
        choices=row.choices,
        condition_key_id=row.condition_key_id,
        condition_label=key.label if key else None,
        reflect_as=row.reflect_as,
        help=row.help,
        sort_order=row.sort_order,
        is_active=row.is_active,
        category_term_ids=[term.id for term in terms],
        categories=[term.value for term in terms],
        usage_count=_definition_usage(db, row.id),
    )


def list_spec_definitions(
    db: Session,
    *,
    include_inactive: bool,
    group_id: uuid.UUID | None = None,
    category_term_id: uuid.UUID | None = None,
) -> list[SpecDefinitionOut]:
    """사양 정의 목록.

    **분류로 거르면 공통도 함께 준다.** 공통 사양은 붙은 분류 행이 없어서, 조인으로
    거르면 통째로 사라진다 — 그러면 전원·무게가 어느 장비 화면에도 안 뜬다.
    """
    stmt = select(SpecDefinition)
    if not include_inactive:
        stmt = stmt.where(SpecDefinition.is_active.is_(True))
    if group_id is not None:
        stmt = stmt.where(SpecDefinition.group_id == group_id)
    if category_term_id is not None:
        matching = select(SpecDefinitionCategory.definition_id).where(
            SpecDefinitionCategory.category_term_id == category_term_id
        )
        common = select(SpecDefinitionCategory.definition_id)
        stmt = stmt.where(SpecDefinition.id.in_(matching) | SpecDefinition.id.not_in(common))
    rows = db.scalars(stmt.order_by(SpecDefinition.sort_order, SpecDefinition.label))
    return [definition_out(db, row) for row in rows]


def get_spec_definition(db: Session, definition_id: uuid.UUID) -> SpecDefinition:
    found = db.get(SpecDefinition, definition_id)
    if found is None:
        raise NotFound("TSC-SPEC-0004", "사양 정의를 찾을 수 없습니다.")
    return found


def _set_definition_categories(
    db: Session, definition: SpecDefinition, term_ids: list[uuid.UUID]
) -> None:
    """붙는 분류를 **통째로 바꾼다.** 빈 목록이면 공통이 된다.

    고를 수 있는 것은 장비 분류 축의 값뿐이다 — 제조사나 시험 항목을 넣으면 그
    사양은 어느 화면에도 안 뜨고, 안 뜨는 이유를 화면이 말해 주지 않는다.
    """
    axis = get_vocabulary(db, "equipment_category")
    for term_id in term_ids:
        term = db.get(VocabularyTerm, term_id)
        if term is None or term.vocabulary_id != axis.id:
            raise AppError(
                "TSC-SPEC-0005", "장비 분류 축의 값만 고를 수 있습니다.", status=400
            )

    for old in db.scalars(
        select(SpecDefinitionCategory).where(
            SpecDefinitionCategory.definition_id == definition.id
        )
    ):
        db.delete(old)
    db.flush()
    for term_id in dict.fromkeys(term_ids):
        db.add(SpecDefinitionCategory(definition_id=definition.id, category_term_id=term_id))


def create_spec_definition(db: Session, *, payload: dict[str, Any]) -> SpecDefinition:
    if (
        db.scalar(select(SpecDefinition).where(SpecDefinition.key == payload["key"]))
        is not None
    ):
        raise Conflict("TSC-SPEC-0006", f"이미 있는 사양 키입니다: {payload['key']}")
    get_spec_group(db, payload["group_id"])

    term_ids: list[uuid.UUID] = payload.pop("category_term_ids", [])
    row = SpecDefinition(**payload)
    db.add(row)
    db.flush()
    _set_definition_categories(db, row, term_ids)
    db.commit()
    db.refresh(row)
    return row


def update_spec_definition(
    db: Session, *, definition_id: uuid.UUID, changes: dict[str, Any], actor: User
) -> SpecDefinition:
    """사양 정의를 고친다.

    **key 와 kind 는 못 바꾼다.** key 는 코드와 반입 스크립트가 걸고 있고, kind 는
    값이 어느 칸에 담겼는지를 정한다 — number 를 text 로 바꾸면 이미 저장된 숫자가
    읽히지 않는 칸에 남는다. 바꾸려면 새로 만들고 옛것을 끈다.

    단위를 바꾸는 것은 조건 정의와 같은 부류다. 이미 저장된 숫자 전부의 뜻이 바뀌니
    감사 기록에 남긴다.
    """
    row = get_spec_definition(db, definition_id)
    before = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "condition_key_id": str(row.condition_key_id) if row.condition_key_id else None,
        "reflect_as": row.reflect_as,
        "is_active": row.is_active,
    }

    if changes.get("group_id") is not None:
        get_spec_group(db, changes["group_id"])
    if "category_term_ids" in changes and changes["category_term_ids"] is not None:
        _set_definition_categories(db, row, changes["category_term_ids"])

    for field, value in changes.items():
        if field == "category_term_ids":
            continue
        # condition_key_id 는 None 으로 지울 일이 있는 칸이지만, 부분 수정에서
        # None 은 "안 바꿈" 이다. 끊으려면 사양을 끄거나 새로 정의한다 —
        # 조용히 끊기면 그 사양이 왜 검색에서 사라졌는지 아무도 못 찾는다.
        if value is not None:
            setattr(row, field, value)

    after = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "condition_key_id": str(row.condition_key_id) if row.condition_key_id else None,
        "reflect_as": row.reflect_as,
        "is_active": row.is_active,
    }
    diff = audit.diff(before, after)
    if diff:
        audit.record(
            db,
            action=audit.SPEC_DEFINITION_CHANGED,
            actor=actor,
            target_table="spec_definitions",
            target_id=row.id,
            target_label=row.label,
            changes=diff,
        )
    db.commit()
    db.refresh(row)
    return row


def delete_spec_definition(db: Session, definition_id: uuid.UUID) -> None:
    """**적힌 값이 있으면 거절한다.** 지우는 대신 끈다(`is_active`) — 지우면 그
    숫자가 무엇이었는지 알 수 없게 된다."""
    row = get_spec_definition(db, definition_id)
    using = _definition_usage(db, row.id)
    if using:
        raise Conflict(
            "TSC-SPEC-0007",
            f"이 사양으로 적힌 값이 {using}개 있습니다. 지우는 대신 끄세요.",
        )
    db.delete(row)
    db.commit()
