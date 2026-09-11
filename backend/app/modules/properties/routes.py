"""물성 ↔ 시험 항목 라우터.

두 자원이다. `/properties` 는 **물성에서 출발하는 눈**(이 물성은 무슨 시험으로 나오나),
`/test-item-properties` 는 연결 한 줄씩의 편집이다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.properties import services
from app.modules.properties.schemas import (
    PropertyOut,
    TestItemPropertyCreateRequest,
    TestItemPropertyOut,
    TestItemPropertyUpdateRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/properties", tags=["properties"])
links_router = APIRouter(prefix="/test-item-properties", tags=["properties"])


@router.get("", response_model=list[PropertyOut])
def list_properties(
    q: str | None = Query(default=None, max_length=200),
    domain: str | None = Query(default=None, max_length=30),
    include_unlinked: bool = Query(default=True),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PropertyOut]:
    """물성 전부와 각각을 내는 시험 항목.

    `include_unlinked=false` 면 **시험 항목이 하나라도 이어진 물성만** — 검색 화면이
    고를 것을 보일 때 쓴다. 이어진 것이 없는 물성을 고르게 두면 결과가 늘 비고, 사람은
    그것을 「우리 장비가 없다」 로 읽는다.
    """
    return services.list_properties(
        db, query=q, domain=domain, include_unlinked=include_unlinked
    )


@links_router.get("", response_model=list[TestItemPropertyOut])
def list_links(
    test_item: uuid.UUID | None = Query(default=None),
    property: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(suggested|confirmed)$"),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[TestItemPropertyOut]:
    return services.list_links(
        db, test_item_term_id=test_item, property_term_id=property, status=status
    )


@links_router.post("", response_model=TestItemPropertyOut, status_code=201)
def create_link(
    payload: TestItemPropertyCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TestItemPropertyOut:
    row = services.create_link(db, user, payload.model_dump())
    return services.link_out(db, row)


@links_router.patch("/{link_id}", response_model=TestItemPropertyOut)
def update_link(
    link_id: uuid.UUID,
    payload: TestItemPropertyUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TestItemPropertyOut:
    """제안을 확인으로 올리거나 단서를 고친다. `status='confirmed'` 가 확인이다."""
    row = services.update_link(db, user, link_id, payload.model_dump(exclude_unset=True))
    return services.link_out(db, row)


@links_router.delete("/{link_id}", status_code=204)
def delete_link(
    link_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete_link(db, user, link_id)
