"""신뢰성 시험 라우터 — 부서가 수행하는 시험. 읽기는 누구나, 쓰기는 그 부서의 관리자."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.reliability import capability as capability_service
from app.modules.reliability import services
from app.modules.reliability.schemas import (
    CapabilityOut,
    ReliabilityTestCreateRequest,
    ReliabilityTestOut,
    ReliabilityTestUpdateRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/reliability-tests", tags=["reliability"])


@router.get("", response_model=list[ReliabilityTestOut])
def list_reliability_tests(
    workspace: str | None = Query(default=None, max_length=64),
    attr: list[str] = Query(default_factory=list, max_length=10),
    status: Literal["candidate", "confirmed", "all"] | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ReliabilityTestOut]:
    """신뢰성 시험 — **부서가 등록한 절차**다. 「시험 항목」(장비가 할 수 있는 측정, 전사
    공용)과 다르다. `workspace` 를 주면 그 부서 것만, 안 주면 전사 전부(부서 순). 시험마다
    쓰는 시험 항목과, 그 항목이 되는 그 부서의 장비 수를 함께 준다 — 0 이면 시험은 정했는데
    돌릴 장비가 없다는 뜻이다.

    `attr` 은 **속성 값으로 거른다** — 여러 번 주면 모두 만족해야 한다(`attr=<키><연산><값>`,
    연산은 `>=` `<=` `>` `<` `=` `!=` `~`(포함) `*`(적혀 있기만 하면)). 왼쪽은 속성 정의의
    `key` 다 — 이름은 관리자가 고치면 바뀌고, 그때 저장해 둔 주소가 조용히 빈 답을 낸다.

    `status` 를 **안 주면 자리에 따라 다르다** — 부서를 주면 후보까지(검토하는 자리라서),
    전사면 확정된 것만(「저 부서가 무슨 시험을 하나」 에 후보는 아직 답이 아니다). 일부러
    보려면 `status="all"`, 후보만 세려면 `status="candidate"`.
    """
    if workspace:
        return services.list_for_workspace(db, user, workspace, attr, status)
    return services.list_all(db, user, attr, status)


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


@router.get("/{test_id}/equipment", response_model=CapabilityOut)
def read_capability(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    """**이 시험을 돌릴 수 있는 장비.** 조건 속성(`kind="condition"`)을 그대로 검색 조건으로
    옮겨 시험 항목마다 장비를 판정한다 — 판정 규칙은 장비 찾기와 같은 것 하나다.

    범위 속성 하나는 물음 둘이 된다(위로 얼마까지 · 아래로 얼마까지). 단위를 축의 SI 로
    못 바꾸는 조건은 빼고 `skipped` 에 이유를 적는다 — 조용히 빼면 조건을 다 본 것처럼
    「가능」 으로 읽힌다.

    부서로 좁히지 않는다. 옆 부서에 있으면 빌리러 가는 것이 이 시스템의 쓸모다.
    """
    return capability_service.capability(db, user, services.get(db, test_id))


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


@router.post("/{test_id}/confirm", response_model=ReliabilityTestOut)
def confirm_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """**후보를 확인했다** — 사람이 내용을 읽고 맞다고 한 것. 그 부서의 관리자 또는 시스템
    관리자만, 그리고 **사람 세션만**(기계 자격은 403). AI 가 스스로 확인할 수 있으면 후보라는
    상태에 아무 뜻이 없다.

    누가 언제 확인했는지가 줄과 감사에 남는다.
    """
    return services.test_out(db, user, services.confirm(db, user, test_id))


@router.post("/{test_id}/reopen", response_model=ReliabilityTestOut)
def reopen_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """확정을 풀어 **다시 후보로.** 그 순간부터 AI 가 다시 채울 수 있으므로, 누가 그 문을
    열었는지가 감사에 남는다. 확인한 사람·시각은 안 지운다."""
    return services.test_out(db, user, services.reopen(db, user, test_id))


@router.delete("/{test_id}", status_code=204)
def delete_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """지우지 않고 `deleted_at` 만 채운다. 감사 기록에 남는다."""
    services.delete(db, user, test_id)
