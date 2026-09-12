"""조건 정의 — 검색이 묻는 축(ConditionKey). 쓰이는 것은 못 지우고 끈다.

`services.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.methods.models import MethodRequirement
from app.modules.test_items.models import (
    EquipmentTestCondition,
)
from app.modules.vocabulary.models import (
    ConditionKey,
)
from app.modules.vocabulary.schemas import (
    ConditionKeyOut,
)
from app.shared import audit
from app.shared.errors import Conflict, NotFound

# --- 조건 정의 ---------------------------------------------------------------


def _condition_usage(db: Session, condition_key_id: uuid.UUID) -> int:
    limits = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentTestCondition)
            .where(EquipmentTestCondition.condition_key_id == condition_key_id)
        )
        or 0
    )
    requirements = (
        db.scalar(
            select(func.count())
            .select_from(MethodRequirement)
            .where(MethodRequirement.condition_key_id == condition_key_id)
        )
        or 0
    )
    return limits + requirements


def condition_out(db: Session, row: ConditionKey) -> ConditionKeyOut:
    return ConditionKeyOut(
        id=row.id,
        key=row.key,
        label=row.label,
        kind=row.kind,
        dimension=row.dimension,
        si_unit=row.si_unit,
        display_unit=row.display_unit,
        choices=row.choices,
        help=row.help,
        sort_order=row.sort_order,
        is_active=row.is_active,
        usage_count=_condition_usage(db, row.id),
    )


def list_conditions(db: Session, *, include_inactive: bool) -> list[ConditionKeyOut]:
    stmt = select(ConditionKey)
    if not include_inactive:
        stmt = stmt.where(ConditionKey.is_active.is_(True))
    rows = db.scalars(stmt.order_by(ConditionKey.sort_order, ConditionKey.label))
    return [condition_out(db, row) for row in rows]


def get_condition(db: Session, condition_id: uuid.UUID) -> ConditionKey:
    found = db.get(ConditionKey, condition_id)
    if found is None:
        raise NotFound("TSC-VOCAB-0008", "조건 정의를 찾을 수 없습니다.")
    return found


def create_condition(db: Session, *, payload: dict[str, Any]) -> ConditionKey:
    if db.scalar(select(ConditionKey).where(ConditionKey.key == payload["key"])) is not None:
        raise Conflict("TSC-VOCAB-0009", f"이미 있는 조건 키입니다: {payload['key']}")
    row = ConditionKey(**payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_condition(
    db: Session, *, condition_id: uuid.UUID, changes: dict[str, Any], actor: User
) -> ConditionKey:
    """조건 정의를 고친다.

    **단위를 바꾸는 것은 되돌릴 수 없는 부류다.** kN 을 N 으로 고치는 순간, 이미
    저장된 숫자 전부가 다른 값이 된다 — 그때 무엇이 바뀌었는지 물을 자리가 감사
    기록밖에 없다. key 는 아예 못 바꾼다: 코드와 검색이 그 이름을 걸고 있다.
    """
    row = get_condition(db, condition_id)
    before = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }

    for field, value in changes.items():
        if value is not None:
            setattr(row, field, value)

    after = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }
    diff = audit.diff(before, after)
    if diff:
        audit.record(
            db,
            action=audit.CONDITION_KEY_CHANGED,
            actor=actor,
            target_table="condition_keys",
            target_id=row.id,
            target_label=row.label,
            changes=diff,
        )
    db.commit()
    db.refresh(row)
    return row
