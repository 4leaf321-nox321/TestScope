"""신뢰성 시험 라우터 — 부서가 수행하는 시험. 읽기는 누구나, 쓰기는 그 부서의 관리자."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.reliability import services
from app.modules.reliability.schemas import (
    ReliabilityTestCreateRequest,
    ReliabilityTestOut,
    ReliabilityTestUpdateRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/reliability-tests", tags=["reliability"])


@router.get("", response_model=list[ReliabilityTestOut])
def list_reliability_tests(
    workspace: str | None = Query(default=None, max_length=64),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ReliabilityTestOut]:
    """신뢰성 시험 — **부서가 등록한 절차**다. 「시험 항목」(장비가 할 수 있는 측정, 전사
    공용)과 다르다. `workspace` 를 주면 그 부서 것만, 안 주면 전사 전부(부서 순). 시험마다
    쓰는 시험 항목과, 그 항목이 되는 그 부서의 장비 수를 함께 준다 — 0 이면 시험은 정했는데
    돌릴 장비가 없다는 뜻이다.
    """
    if workspace:
        return services.list_for_workspace(db, user, workspace)
    return services.list_all(db, user)


@router.post("", response_model=ReliabilityTestOut, status_code=201)
def create_reliability_test(
    payload: ReliabilityTestCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """등록 — 그 부서의 관리자 또는 시스템 관리자. `test_item_term_ids` 는 시험 항목 축의
    값이어야 한다(`POST /api/resolve` 로 먼저 찾는다)."""
    row = services.create(db, user, payload.model_dump())
    return services.test_out(db, user, row)


@router.get("/{test_id}", response_model=ReliabilityTestOut)
def read_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    return services.test_out(db, user, services.get(db, test_id))


@router.patch("/{test_id}", response_model=ReliabilityTestOut)
def update_reliability_test(
    test_id: uuid.UUID,
    payload: ReliabilityTestUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """부분 수정. 안 보낸 칸은 그대로, `test_item_term_ids` 는 보내면 통째로 바뀐다."""
    row = services.update(db, user, test_id, payload.model_dump(exclude_unset=True))
    return services.test_out(db, user, row)


@router.delete("/{test_id}", status_code=204)
def delete_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """지우지 않고 `deleted_at` 만 채운다. 감사 기록에 남는다."""
    services.delete(db, user, test_id)
