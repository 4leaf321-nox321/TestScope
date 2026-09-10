"""시험 항목 라우터.

목록이 **장비 아래**에 있다. 시험 항목은 홀로 서는 자원이 아니라 장비의 능력이고,
그래서 목록을 부르는 자리도 장비다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.test_items import services
from app.modules.test_items.schemas import (
    EquipmentTestItemCreateRequest,
    EquipmentTestItemOut,
    EquipmentTestItemUpdateRequest,
    LimitOut,
    LimitUpsertRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/equipment-test-items", tags=["test-items"])


@router.get("", response_model=list[EquipmentTestItemOut])
def list_test_items(
    equipment_id: uuid.UUID = Query(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[EquipmentTestItemOut]:
    return services.list_for_equipment(db, user, equipment_id)


@router.post("", response_model=EquipmentTestItemOut, status_code=201)
def create_test_item(
    payload: EquipmentTestItemCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentTestItemOut:
    row = services.create(db, user, payload.model_dump())
    return services.test_item_out(db, row, user)


@router.patch("/{equipment_test_item_id}", response_model=EquipmentTestItemOut)
def update_test_item(
    equipment_test_item_id: uuid.UUID,
    payload: EquipmentTestItemUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentTestItemOut:
    row = services.update(
        db, user, equipment_test_item_id, payload.model_dump(exclude_unset=True)
    )
    return services.test_item_out(db, row, user)


@router.delete("/{equipment_test_item_id}", status_code=204)
def delete_test_item(
    equipment_test_item_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete(db, user, equipment_test_item_id)


@router.put("/{equipment_test_item_id}/limits", response_model=LimitOut)
def upsert_limit(
    equipment_test_item_id: uuid.UUID,
    payload: LimitUpsertRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> LimitOut:
    return services.upsert_limit(db, user, equipment_test_item_id, payload.model_dump())


@router.delete("/{equipment_test_item_id}/limits/{limit_id}", status_code=204)
def delete_limit(
    equipment_test_item_id: uuid.UUID,
    limit_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete_limit(db, user, equipment_test_item_id, limit_id)
