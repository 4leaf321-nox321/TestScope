"""항목 정의 라우터 — 읽기는 누구나(입력 칸이 목록을 보여 줘야 한다), 쓰기는 시스템 관리자.

값은 여기 없다. 값은 붙는 대상의 API 가 함께 받는다(`POST /reliability-tests` 의 `attributes`).
초안은 그 길로 생긴다 — 여기서 만드는 것은 관리자가 미리 준비하는 정의다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.attributes import filters as attribute_filters
from app.modules.attributes import services
from app.modules.attributes.schemas import (
    AttributeDefinitionCreateRequest,
    AttributeDefinitionOut,
    AttributeDefinitionUpdateRequest,
    AttributeFilterDiagnosisOut,
    AttributeMergeRequest,
)
from app.shared.auth import current_user, require_system_admin
from app.shared.permissions import visible_equipment_ids

router = APIRouter(prefix="/attribute-definitions", tags=["attributes"])


@router.get("", response_model=list[AttributeDefinitionOut])
def list_attribute_definitions(
    target: str = Query(..., max_length=20),
    include_inactive: bool = Query(default=False),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AttributeDefinitionOut]:
    """한 대상(`reliability_test` · `equipment`)에 붙는 항목 정의 — 정식이 먼저, 초안이 뒤.
    `value_count` 는 그 항목으로 적힌 값의 수다. 초안을 건수순으로 보면 무엇을 정식으로
    올릴지 보인다."""
    return services.list_definitions(db, target=target, include_inactive=include_inactive)


@router.get("/diagnose", response_model=list[AttributeFilterDiagnosisOut])
def diagnose_filters(
    target: str = Query(..., max_length=20),
    attr: list[str] = Query(default_factory=list, max_length=10),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AttributeFilterDiagnosisOut]:
    """속성 조건으로 거른 목록이 **0건일 때** 부른다 — 조건마다 왜 아무것도 못 걸렀나.

    빈 목록은 「아무도 안 적었다」 「조건이 좁다」 「단위를 못 바꿨다」 「조건끼리 겹쳐
    비었다」 를 똑같이 생겼다. 조건마다 값이 적힌 수 · 단위 못 바꾼 수 · 그 조건 하나로
    걸리는 수와 한 줄 안내를 준다. 문법과 대상은 목록의 `attr` 과 같다. 장비는 **내가 볼 수
    있는 것**만 센다 — 목록과 같은 규칙이라야 「목록엔 없는데 진단엔 있다」 가 안 생긴다.
    """
    parsed = attribute_filters.parse(db, target, attr)
    base = visible_equipment_ids(db, user) if target == "equipment" else None
    return [
        AttributeFilterDiagnosisOut(**one.__dict__)
        for one in attribute_filters.diagnose(db, target, parsed, base=base)
    ]


@router.post("", response_model=AttributeDefinitionOut, status_code=201)
def create_attribute_definition(
    payload: AttributeDefinitionCreateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> AttributeDefinitionOut:
    """정식 항목을 만든다. `status="draft"` 로 보내면 조사 중인 후보를 미리 목록에 세운다."""
    row = services.create_definition(db, admin, payload.model_dump())
    return services.definition_out(db, row)


@router.patch("/{definition_id}", response_model=AttributeDefinitionOut)
def update_attribute_definition(
    definition_id: uuid.UUID,
    payload: AttributeDefinitionUpdateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> AttributeDefinitionOut:
    """부분 수정. 정식으로 올리기는 `{"status": "standard"}`. 종류는 값이 없을 때만 바뀐다."""
    row = services.update_definition(db, definition_id, payload.model_dump(exclude_unset=True))
    return services.definition_out(db, row)


@router.delete("/{definition_id}", status_code=204)
def delete_attribute_definition(
    definition_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    """값이 하나도 없는 항목만 지운다(오타 초안). 값이 있으면 409 — 끄거나 합친다."""
    services.delete_definition(db, definition_id)


@router.post("/{definition_id}/merge", response_model=AttributeDefinitionOut)
def merge_attribute_definition(
    definition_id: uuid.UUID,
    payload: AttributeMergeRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> AttributeDefinitionOut:
    """이름만 다른 항목을 `target_id` 로 합친다. 값이 옮겨 가고 이 항목은 꺼진다. 종류가 같아야
    한다."""
    row = services.merge_into(db, definition_id, payload.target_id)
    return services.definition_out(db, row)
