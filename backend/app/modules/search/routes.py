"""검색 라우터.

**POST 다.** 조건이 스무 개까지 들어갈 수 있어 주소에 실으면 길이 제한에 걸리고,
무엇을 물었는지는 서버 로그에도 주소보다 몸통이 맞다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.search import catalog_search, services
from app.modules.search.schemas import (
    CatalogSearchResponse,
    ConditionQuery,
    SearchRequest,
    SearchResponse,
    SemanticHit,
    SemanticSearchResponse,
)
from app.shared import semantic
from app.shared.auth import current_user
from app.shared.permissions import visible_equipment_ids

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


@router.get("/semantic", response_model=SemanticSearchResponse)
def search_semantic(
    q: str = Query(..., min_length=1, max_length=500),
    kind: list[str] | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=40),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SemanticSearchResponse:
    """뜻이 가까운 시험 항목·물성·계열·기종·규격·보유 장비·신뢰성 시험.

    자유 문장으로 물을 때의 첫 손잡이다 — 「HAST」 「thermal shock」 「얇은 판 잡아당기는
    규격」. 답은 **후보**다: 시험 항목이 정해지면 `POST /search/test-items` 로 조건을 붙여
    장비를 찾고, 이름이 하나로 정해졌는지는 `POST /resolve` 가 말한다. `kind` 로 종류를
    거른다(여러 개 가능). 보유 장비는 이 사람이 볼 수 있는 것만 온다 — 목록·검색과 같은 규칙.
    부품(pgvector·Ollama)이 없으면 `available=false` 에 빈 목록 — 오류가 아니다.
    """
    unknown = [one for one in (kind or []) if one not in semantic.KINDS]
    if unknown:
        return SemanticSearchResponse(available=semantic.available(db), hits=[])
    visible = None
    if not user.is_system_admin:
        visible = [str(one) for one in db.scalars(visible_equipment_ids(db, user))]
    found = semantic.search(db, q, kinds=kind or None, visible_equipment=visible, limit=limit)
    return SemanticSearchResponse(
        available=semantic.available(db),
        hits=[
            SemanticHit(
                kind=one.kind,
                id=one.entity_id,
                title=one.title,
                snippet=one.snippet,
                score=round(one.score, 4),
            )
            for one in found
        ],
    )


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
