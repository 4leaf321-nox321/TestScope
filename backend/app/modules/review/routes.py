"""검토함 라우터 — 시스템 관리자(도메인 전문가)가 후보 중에서 고른다."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.review import services
from app.modules.review.schemas import (
    DecideRequest,
    ProposalOut,
    ProposalPage,
    QueueOut,
    RefreshResult,
)
from app.shared.auth import current_user, require_system_admin

router = APIRouter(prefix="/review", tags=["review"])


@router.get("", response_model=list[QueueOut])
def list_queues(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[QueueOut]:
    """물음 넷과 각각 몇 건이 열려 있나. **0 이면 그 물음은 끝난 것이다.**"""
    return services.queues(db)


@router.get("/{queue}", response_model=ProposalPage)
def list_proposals(
    queue: str,
    status: str = Query(default="open", pattern="^(open|decided|skipped|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProposalPage:
    """한 물음의 줄들 — 대상 · 후보(추천과 근거) · 상세 링크."""
    items, total = services.list_proposals(
        db, queue, status=status, limit=limit, offset=offset
    )
    return ProposalPage(items=items, total=total)


@router.post("/{queue}/{proposal_id}/decide", response_model=ProposalOut)
def decide(
    queue: str,
    proposal_id: uuid.UUID,
    payload: DecideRequest,
    user: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """고른다. 기존 규칙(규격 → 인용 계열에 붙임, 사양 → 같은 키 함께 올림)이 그대로 돈다.
    **누가 골랐고 추천을 따랐는지**가 감사와 이 줄에 남는다."""
    row = services.decide(db, user, proposal_id, choice=payload.choice, note=payload.note)
    return services.proposal_out(row)


@router.post("/{queue}/{proposal_id}/skip", response_model=ProposalOut)
def skip(
    queue: str,
    proposal_id: uuid.UUID,
    user: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """건너뛴다(다시 누르면 되돌린다). 결정이 아니라 「지금은 모르겠다」 다."""
    return services.proposal_out(services.skip(db, user, proposal_id))


@router.post("/refresh", response_model=RefreshResult)
def refresh(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> RefreshResult:
    """후보를 다시 세운다 — 반입 뒤나 정본(`proposals/`)을 고친 뒤. 화면에서 이미 정한 것은
    결정으로 닫힌다."""
    counts = services.refresh(db)
    db.commit()
    return RefreshResult(open=counts)
