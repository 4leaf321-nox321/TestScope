"""기준정보 허브 — 연계 설정 · 현황 · 이력은 **시스템 관리자**, 받은 데이터 조회는 누구나.

`/api/hub` 는 기계 자격의 쓰기 범위 표(`auth._WRITE_SCOPES`)에 없다 — 연계 설정과 수동 실행은
사람이 화면에서 한다. 읽기(받은 데이터 조회)는 토큰으로도 된다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.hub import services
from app.modules.hub.schemas import (
    HubCheckOut,
    HubConnectionOut,
    HubConnectionRequest,
    HubItemDetailOut,
    HubItemPage,
    HubPublicTypeOut,
    HubRunOut,
    HubRunQueued,
    HubRunRequest,
    HubStatusOut,
)
from app.shared.auth import current_user, require_system_admin

router = APIRouter(prefix="/hub", tags=["hub"])


@router.get("/connection", response_model=HubConnectionOut)
def read_connection(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> HubConnectionOut:
    """연계 설정. 토큰은 **설정됨 여부만** — 평문은 다시 안 보인다."""
    return services.connection_out(db)


@router.put("/connection", response_model=HubConnectionOut)
def update_connection(
    payload: HubConnectionRequest,
    user: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> HubConnectionOut:
    return services.update_connection(db, user, payload.model_dump())


@router.post("/check", response_model=HubCheckOut)
def check(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> HubCheckOut:
    """연결 점검 — 카탈로그를 받아 본다. 공개 타입이 타입 고르기에 선다."""
    return services.check(db)


@router.post("/catalog-seen", status_code=204)
def catalog_seen(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> None:
    """구조 변경 알림을 확인했다."""
    services.seen_catalog_change(db)


@router.get("/status", response_model=HubStatusOut)
def status(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> HubStatusOut:
    """수신 현황 — 타입마다 기준 시각 · 마지막 수신 · 건수(카탈로그 수와 견줌) · 결과."""
    return services.status(db)


@router.post("/run", response_model=HubRunQueued, status_code=202)
def run(
    payload: HubRunRequest,
    user: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> HubRunQueued:
    """수동 실행 — 워커가 받는다. `full` 이면 전량 수신과 부재 대조."""
    job = services.request_run(db, user, full=payload.full)
    return HubRunQueued(job_id=job.id, full=payload.full)


@router.get("/runs", response_model=list[HubRunOut])
def runs(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> list[HubRunOut]:
    """수신 이력 — 실행마다 타입별 건수 · 결과 · 오류 · `request_id`."""
    return services.runs(db, limit=limit, offset=offset)


@router.get("/types", response_model=list[HubPublicTypeOut])
def public_types(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[HubPublicTypeOut]:
    """받아 둔 타입 — 누구나."""
    return services.public_types(db)


@router.get("/types/{type_slug}/items", response_model=HubItemPage)
def items(
    type_slug: str,
    q: str | None = Query(default=None, max_length=200),
    state: str | None = Query(default=None, pattern="^(active|inactive)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> HubItemPage:
    """받은 객체 목록 — 식별자 · 이름 검색, 상태(사용 · 사용 중지 · 병합 …)."""
    return services.items(db, type_slug, q=q, state=state, limit=limit, offset=offset)


@router.get("/types/{type_slug}/items/{key}", response_model=HubItemDetailOut)
def item_detail(
    type_slug: str,
    key: str,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> HubItemDetailOut:
    """받은 객체 하나와 관계. 옛 식별자로 물어도 지금 객체를 준다."""
    return services.item_detail(db, type_slug, key)
