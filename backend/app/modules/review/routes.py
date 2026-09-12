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
    VoteRequest,
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
    status: str = Query(default="open", pattern="^(open|voted|decided|skipped|gone|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProposalPage:
    """한 물음의 줄들 — 대상 · 후보(추천과 근거) · 모인 의견 · 상세 링크.
    `status=voted` 는 열린 것 중 의견이 모인 줄."""
    items, total = services.list_proposals(
        db, queue, status=status, limit=limit, offset=offset, viewer_id=user.id
    )
    return ProposalPage(items=items, total=total)


@router.post("/{queue}/{proposal_id}/vote", response_model=ProposalOut)
def vote(
    queue: str,
    proposal_id: uuid.UUID,
    payload: VoteRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """의견을 낸다 — **로그인한 누구나.** 확정이 아니라 데이터는 안 바뀐다. 사람당 한 줄에
    하나, 다시 내면 바뀐다."""
    row = services.vote(db, user, proposal_id, choice=payload.choice, note=payload.note)
    return services.with_votes(db, row, user.id)


@router.delete("/{queue}/{proposal_id}/vote", response_model=ProposalOut)
def withdraw_vote(
    queue: str,
    proposal_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """내 의견을 거둔다."""
    return services.with_votes(db, services.withdraw_vote(db, user, proposal_id), user.id)


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
    return services.with_votes(db, row, user.id)


@router.post("/{queue}/{proposal_id}/skip", response_model=ProposalOut)
def skip(
    queue: str,
    proposal_id: uuid.UUID,
    user: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """건너뛴다(다시 누르면 되돌린다). 결정이 아니라 「지금은 모르겠다」 다."""
    return services.with_votes(db, services.skip(db, user, proposal_id), user.id)


@router.post("/{queue}/{proposal_id}/reopen", response_model=ProposalOut)
def reopen(
    queue: str,
    proposal_id: uuid.UUID,
    user: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """정한 것을 다시 연다 — 다른 걸로 고르려고. 이미 일어난 일(지운 연결·만든 정의)은
    안 되돌린다; 그건 원래 화면에서."""
    return services.with_votes(db, services.reopen(db, user, proposal_id), user.id)


@router.post("/refresh", response_model=RefreshResult)
def refresh(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> RefreshResult:
    """후보를 다시 세운다 — 반입 뒤나 정본(`proposals/`)을 고친 뒤. 화면에서 이미 정한 것은
    결정으로 닫힌다."""
    counts = services.refresh(db)
    db.commit()
    return RefreshResult(open=counts)
