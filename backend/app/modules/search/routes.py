"""검색 라우터.

**POST 다.** 조건이 스무 개까지 들어갈 수 있어 주소에 실으면 길이 제한에 걸리고,
무엇을 물었는지는 서버 로그에도 주소보다 몸통이 맞다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.search import catalog_search, services
from app.modules.search.schemas import (
    CatalogSearchResponse,
    ConditionQuery,
    SearchRequest,
    SearchResponse,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/test-items", response_model=SearchResponse)
def search_test_items(
    payload: SearchRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    return services.search(db, user, payload)


@router.post("/catalog", response_model=CatalogSearchResponse)
def search_catalog(
    payload: SearchRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CatalogSearchResponse:
    """「이 시험을 하려면 어떤 기종이 되나 / 사야 하나」 — 카탈로그에서 찾는다.

    같은 물음(`SearchRequest`)을 받는다. 장비 검색이 우리가 가진 것을 답할 때 이것은
    세상에 있는 것을 답한다 — 가진 것이 없을 때 다음 물음은 늘 「그러면 무엇을 사나」 다.
    """
    return catalog_search.search_catalog(db, user, payload)


@router.get("/method-conditions/{method_id}", response_model=list[ConditionQuery])
def method_conditions(
    method_id: uuid.UUID,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ConditionQuery]:
    """규격 하나가 요구하는 조건을 검색 물음으로 바꿔 준다.

    화면이 이것을 받아 조건 칸을 채운다 — 아니면 사람이 규격서를 펴 놓고 숫자를
    옮겨 적어야 하고, 그 옮겨 적기에서 자릿수가 틀린다.
    """
    return services.method_conditions(db, method_id)
