"""검토함 — **후보와 근거를 먼저 보여 주고, 도메인 전문가가 고른다.**

## 왜 있나

반입이 못 정한 것(어느 시험의 규격인가 · 이 물성이 이 시험에서 나오나 · 이 시험은 무슨 조건을
묻나)은 흩어진 화면마다 「미정」 으로 서 있었다. 정하는 손잡이는 있었지만 **무엇을 골라야
하는지 후보와 근거가 안 보여서** 결정하려면 규격마다 상세를 열어야 했다.

여기서는 한 줄에 **후보 · 추천 · 왜 그렇게 생각하는지**를 놓고, 고르면 기존 API 가 그대로
움직인다. 추천은 정본(`source/catalog/proposals/*.json`)에서 오고, 개발자가 아니라
**도메인 전문가가 최종 판단**한다 — 그래서 누가 골랐고 추천을 따랐는지가 남는다.

## 추천은 정답이 아니다

첫 보기를 습관적으로 누르게 되므로 근거를 옆에 적고, 확신이 낮은 것에는 추천을 안 붙이며,
「직접 고르기」 와 「건너뛰기」 를 늘 둔다. `followed` 로 추천을 따랐는지가 남아, 어느 종류의
추천이 얼마나 틀리는지 나중에 볼 수 있다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReviewProposal(Base):
    """검토할 것 하나 — 대상 · 후보들 · 추천 · 결정."""

    __tablename__ = "review_proposals"
    __table_args__ = (
        UniqueConstraint("queue", "subject_key", name="uq_review_proposals_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    queue: Mapped[str] = mapped_column(String(40), index=True)
    """어느 물음인가 — `method_test_items` · `test_item_axes` · `property_links` ·
    `free_spec_definitions`. 물음마다 후보의 뜻과 적용 방법이 다르다(`services.QUEUES`)."""

    subject_key: Mapped[str] = mapped_column(String(200))
    """정본과 잇는 열쇠 — 규격은 `method_key`, 시험 항목은 코드, 연결은 `항목:물성`,
    사양은 `원본 키|단위`. id 가 아니라 열쇠로 두는 이유: 정본의 결정을 다른 설치(운영)에
    들일 때 id 는 다르고 열쇠는 같다."""
    subject_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    """이 설치에서의 대상 행 id. 화면이 상세로 가는 링크."""
    subject_label: Mapped[str] = mapped_column(String(300))
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    """이 줄이 정확히 무엇을 묻는지 — 완전한 문장. 「3400」 만 주고 「무슨 시험을 하나」 를
    묻지 않게(review/facts.py)."""
    facts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    """대상을 이해하는 사실 몇 줄 — {label, value, link}. 제조사·분류·소개·지금 하는 시험 …"""
    """대상을 이해하는 데 필요한 한 줄 — 「인용: Unholtz-Dickie 진동 시험기」 같은 것."""

    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    """`[{"code", "label", "recommended", "reason"}]`. 추천은 많아야 하나."""
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    """적용에 필요한 덧붙임 — 사양을 정의로 올릴 때의 키·그룹·종류 같은 것."""

    status: Mapped[str] = mapped_column(
        String(20), default="open", server_default="open", index=True
    )
    """open · decided · skipped · gone. 건너뛴 것은 다시 뜬다; 정한 것은 「다시 열기」 로
    열린다; gone 은 대상(규격·연결·사양 줄)이 지워져 물음 자체가 없어진 것이라 안 열린다."""
    choice: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    """고른 후보 코드들. 빈 목록은 「해당 없음」 — 축이 없는 게 맞다 같은 결정."""
    followed: Mapped[bool | None] = mapped_column(nullable=True)
    """추천을 따랐나. 추천이 없었으면 NULL."""
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_by_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """그때의 이름. 계정이 지워져도 「누가 정했나」 는 남아야 한다."""
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ReviewVote(Base):
    """한 사람의 **의견** — 확정이 아니다. 데이터를 건드리지 않고 모이기만 한다.

    여럿이 갈리는 줄이 눈에 보이게(「3명 중 2:1」) 하려는 것이다. 사람당 한 줄에 하나,
    바꿀 수 있고 거둘 수 있다. 확정(`ReviewProposal.choice`)은 시스템 관리자가 따로 한다 —
    의견 없이도 확정할 수 있어 사람이 적을 때 느려지지 않는다.
    """

    __tablename__ = "review_votes"
    __table_args__ = (UniqueConstraint("proposal_id", "user_id", name="uq_review_votes_user"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("review_proposals.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user_label: Mapped[str] = mapped_column(String(200))
    """그때의 이름. 계정이 지워져도 누구 의견이었는지 남는다."""
    choice: Mapped[list[str]] = mapped_column(JSONB, default=list)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
