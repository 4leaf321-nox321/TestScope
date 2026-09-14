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
from app.modules.test_items import catalog, services
from app.modules.test_items.schemas import (
    EquipmentTestItemCreateRequest,
    EquipmentTestItemOut,
    EquipmentTestItemUpdateRequest,
    LimitOut,
    LimitUpsertRequest,
    TestItemCatalogOut,
    TestItemCatalogRow,
    TestItemConditionKeysRequest,
)
from app.shared.auth import current_user, require_system_admin

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


catalog_router = APIRouter(prefix="/test-items", tags=["test-items"])


@catalog_router.get("", response_model=list[TestItemCatalogRow])
def list_test_item_catalog(
    workspace: str | None = Query(default=None, max_length=64),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[TestItemCatalogRow]:
    """시험 항목 카탈로그 — 항목마다 **사슬 전체의 수**(물성·규격·계열·기종·보유 장비·검색축).

    0 이 곧 공백이다. 「물성 없는 시험 항목」 「규격 없는 시험 항목」 을 여기서 거른다.
    보유 장비는 내가 볼 수 있는 것만 센다 — 검색과 같은 규칙.

    `workspace` 에 부서 주소를 주면 보유 장비를 **그 부서 것만** 센다 — 「저 부서는 무슨
    시험을 하나」 의 답이고, 0 인 줄이 곧 그 부서가 못 하는 시험이다. 나머지 수는
    전사 공용 정의라 그대로다.
    """
    return catalog.list_rows(db, user, workspace_slug=workspace)


@catalog_router.get("/{term_id}", response_model=TestItemCatalogOut)
def read_test_item(
    term_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TestItemCatalogOut:
    """시험 항목 하나 — 얻는 물성 · 규격 · 되는 계열 · 보유 장비 · 검색축을 한 자리에."""
    return catalog.detail(db, user, term_id)


@catalog_router.put("/{term_id}/condition-keys", status_code=204)
def set_test_item_condition_keys(
    term_id: uuid.UUID,
    payload: TestItemConditionKeysRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    """이 시험 항목에 **뜻이 있는 조건 축**을 정한다(통째로 바꾼다).

    인장은 하중·속도·온도, 챔버는 온도·습도. 전에는 어디에도 없어 검색이 축 일곱 개를 다
    물었다. 전사 공용 지식이라 시스템 관리자가 정한다.
    """
    catalog.set_condition_keys(db, term_id, payload.condition_key_ids)
