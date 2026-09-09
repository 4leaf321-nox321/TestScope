"""이름으로 찾기 라우터.

**AI 가 만들기 전에 반드시 부르는 도구다.** 없으면 목록 검색으로 흉내내야 하고,
흉내는 매번 조금씩 다르게 틀린다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.resolve import services
from app.modules.resolve.schemas import ResolveRequest, ResolveResponse
from app.shared.auth import current_user

router = APIRouter(prefix="/resolve", tags=["resolve"])


@router.post("", response_model=ResolveResponse)
def resolve(
    payload: ResolveRequest,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ResolveResponse:
    """이름으로 계열·기종·기준정보 값·시험법을 찾는다.

    **무엇을 만들기 전에 이것을 먼저 부른다.** 응답의 `match` 가 셋이다:

        exact       하나로 정해졌다. `id` 를 그대로 쓴다
        candidates  여럿이다. 고르지 말고 사람에게 묻는다
        none        없다. 새로 만들거나 비워 둔다 — **지어내지 않는다**

    못 찾은 것은 실패가 아니라서 언제나 200 이다. `hint` 에 다음에 할 일이 한 줄로
    적혀 있다.
    """
    return services.resolve(db, payload.model_dump())
