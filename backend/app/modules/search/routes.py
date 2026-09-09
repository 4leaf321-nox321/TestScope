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
from app.modules.search import services
from app.modules.search.schemas import ConditionQuery, SearchRequest, SearchResponse
from app.shared.auth import current_user

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/capabilities", response_model=SearchResponse)
def search_capabilities(
    payload: SearchRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    return services.search(db, user, payload)


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
