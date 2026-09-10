"""시험 항목 로직.

시험 항목을 고칠 수 있는 사람은 **그 장비를 고칠 수 있는 사람**이다. 별도의 권한 축을
두지 않는다 — 두면 "장비는 못 고치는데 그 장비의 능력은 고치는" 상태가 생기고,
그것은 설명할 수 없다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment
from app.modules.methods.models import TestMethod
from app.modules.test_items.models import EquipmentTestCondition, EquipmentTestItem
from app.modules.test_items.schemas import EquipmentTestItemOut, LimitOut
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.permissions import get_equipment, require_owner_edit

_WHAT = "장비"
_CODE = "TSC-CAPABILITIES-0002"


def _limits(db: Session, equipment_test_item_id: uuid.UUID) -> list[LimitOut]:
    rows = db.execute(
        select(EquipmentTestCondition, ConditionKey)
        .join(ConditionKey, ConditionKey.id == EquipmentTestCondition.condition_key_id)
        .where(EquipmentTestCondition.equipment_test_item_id == equipment_test_item_id)
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all()
    return [
        LimitOut(
            id=limit.id,
            condition_key_id=key.id,
            condition_key=key.key,
            condition_label=key.label,
            si_unit=key.si_unit,
            display_unit=key.display_unit,
            min_value=limit.min_value,
            max_value=limit.max_value,
            text_value=limit.text_value,
            note=limit.note,
        )
        for limit, key in rows
    ]


def _can_edit(db: Session, user: User, equipment: Equipment) -> bool:
    try:
        require_owner_edit(db, user, equipment.owner_workspace_id, what=_WHAT, code=_CODE)
    except AppError:
        return False
    return True


def test_item_out(db: Session, row: EquipmentTestItem, viewer: User) -> EquipmentTestItemOut:
    equipment = db.get(Equipment, row.equipment_id)
    item = db.get(VocabularyTerm, row.test_item_term_id)
    method = db.get(TestMethod, row.method_id) if row.method_id else None
    return EquipmentTestItemOut(
        id=row.id,
        equipment_id=row.equipment_id,
        equipment_asset_no=equipment.asset_no if equipment else "",
        equipment_name=equipment.name if equipment else "",
        test_item_term_id=row.test_item_term_id,
        test_item=item.value if item else "",
        method_id=row.method_id,
        method_code=f"{method.code} {method.edition or ''}".strip() if method else None,
        confidence=row.confidence,
        verified_on=row.verified_on,
        note=row.note,
        limits=_limits(db, row.id),
        created_at=row.created_at,
        can_edit=_can_edit(db, viewer, equipment) if equipment else False,
    )


def list_for_equipment(
    db: Session, user: User, equipment_id: uuid.UUID
) -> list[EquipmentTestItemOut]:
    # 볼 수 있는 장비인지부터 판정한다 — 시험 항목만 따로 열어 두면 가려 둔 부서의
    # 장비 능력이 그 길로 새어 나간다.
    get_equipment(db, user, equipment_id)
    rows = db.scalars(
        select(EquipmentTestItem)
        .where(EquipmentTestItem.equipment_id == equipment_id)
        .order_by(EquipmentTestItem.created_at)
    )
    return [test_item_out(db, row, user) for row in rows]


def get_test_item(
    db: Session, user: User, equipment_test_item_id: uuid.UUID
) -> EquipmentTestItem:
    row = db.get(EquipmentTestItem, equipment_test_item_id)
    if row is None:
        raise NotFound("TSC-CAPABILITIES-0001", "시험 항목을 찾을 수 없습니다.")
    get_equipment(db, user, row.equipment_id)
    return row


def create(db: Session, user: User, payload: dict[str, Any]) -> EquipmentTestItem:
    equipment = get_equipment(db, user, payload["equipment_id"])
    require_owner_edit(db, user, equipment.owner_workspace_id, what=_WHAT, code=_CODE)

    method_id = payload.get("method_id")
    clash = db.scalar(
        select(EquipmentTestItem).where(
            EquipmentTestItem.equipment_id == equipment.id,
            EquipmentTestItem.test_item_term_id == payload["test_item_term_id"],
            EquipmentTestItem.method_id.is_(None)
            if method_id is None
            else EquipmentTestItem.method_id == method_id,
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-CAPABILITIES-0003",
            "같은 시험 항목·시험법의 시험 항목이 이미 있습니다. 그것을 고치세요.",
            details={"equipment_test_item_id": str(clash.id)},
        )

    row = EquipmentTestItem(
        equipment_id=equipment.id,
        test_item_term_id=payload["test_item_term_id"],
        method_id=method_id,
        confidence=payload.get("confidence", "catalog"),
        verified_on=payload.get("verified_on"),
        note=payload.get("note"),
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update(
    db: Session, user: User, equipment_test_item_id: uuid.UUID, changes: dict[str, Any]
) -> EquipmentTestItem:
    row = get_test_item(db, user, equipment_test_item_id)
    equipment = db.get(Equipment, row.equipment_id)
    require_owner_edit(
        db, user, equipment.owner_workspace_id if equipment else None, what=_WHAT, code=_CODE
    )

    for field in ("method_id", "confidence", "verified_on", "note"):
        if field in changes:
            setattr(row, field, changes[field])
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, equipment_test_item_id: uuid.UUID) -> None:
    row = get_test_item(db, user, equipment_test_item_id)
    equipment = db.get(Equipment, row.equipment_id)
    require_owner_edit(
        db, user, equipment.owner_workspace_id if equipment else None, what=_WHAT, code=_CODE
    )
    db.delete(row)
    db.commit()


def upsert_limit(
    db: Session, user: User, equipment_test_item_id: uuid.UUID, payload: dict[str, Any]
) -> LimitOut:
    """조건 한 칸을 넣거나 덮어쓴다. 같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없다."""
    row = get_test_item(db, user, equipment_test_item_id)
    equipment = db.get(Equipment, row.equipment_id)
    require_owner_edit(
        db, user, equipment.owner_workspace_id if equipment else None, what=_WHAT, code=_CODE
    )

    key = db.get(ConditionKey, payload["condition_key_id"])
    if key is None:
        raise NotFound("TSC-CAPABILITIES-0004", "조건 정의를 찾을 수 없습니다.")

    low, high = payload.get("min_value"), payload.get("max_value")
    if low is not None and high is not None and low > high:
        # **거꾸로 넣은 범위는 검색에서 아무것도 안 맞는다.** 조용히 통과시키면
        # 사람은 "왜 우리 장비가 안 나오지" 를 묻게 되고, 그 원인은 안 보인다.
        raise AppError(
            "TSC-CAPABILITIES-0005",
            f"{key.label}의 최소가 최대보다 큽니다.",
            status=400,
        )

    existing = db.scalar(
        select(EquipmentTestCondition).where(
            EquipmentTestCondition.equipment_test_item_id == row.id,
            EquipmentTestCondition.condition_key_id == key.id,
        )
    )
    target = existing or EquipmentTestCondition(
        equipment_test_item_id=row.id, condition_key_id=key.id
    )
    target.min_value = low
    target.max_value = high
    target.text_value = payload.get("text_value")
    target.note = payload.get("note")
    if existing is None:
        db.add(target)
    db.commit()

    return next(one for one in _limits(db, row.id) if one.condition_key_id == key.id)


def delete_limit(
    db: Session, user: User, equipment_test_item_id: uuid.UUID, limit_id: uuid.UUID
) -> None:
    row = get_test_item(db, user, equipment_test_item_id)
    equipment = db.get(Equipment, row.equipment_id)
    require_owner_edit(
        db, user, equipment.owner_workspace_id if equipment else None, what=_WHAT, code=_CODE
    )
    target = db.get(EquipmentTestCondition, limit_id)
    if target is None or target.equipment_test_item_id != row.id:
        raise NotFound("TSC-CAPABILITIES-0006", "조건을 찾을 수 없습니다.")
    db.delete(target)
    db.commit()
