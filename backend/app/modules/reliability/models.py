"""신뢰성 시험 — **부서가 제품 개발·검증을 위해 수행하는 시험.**

「시험 항목」 과 다른 층이다. 시험 항목은 장비가 할 수 있는 측정(인장·경도·열충격)이고
전사 공용 정의라 카탈로그에 산다. 신뢰성 시험은 「고온고습 1000h」 「열충격 500 cycle」
처럼 **부서가 정한 절차**이며, 시험 항목 하나 이상을 써서 돈다. 그래서 사슬은

    신뢰성 시험  →  시험 항목  →  (조건 · 시험법)  →  장비  →  보유 위치

로, 기존 사슬 위에 한 층이 얹힌다 — 아래 사슬은 건드리지 않는다.

**칸은 아직 조사 중이다.** 이름과 목적, 쓰는 시험 항목만 두고 나머지(조건·판정 기준·
근거 규격·주기)는 현장의 목록을 보고 더한다. 지어내면 그 칸은 아무도 안 채운다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReliabilityTest(Base):
    __tablename__ = "reliability_tests"
    __table_args__ = (
        # 같은 부서에 같은 이름은 하나 — 지운 것은 빼고(부분 유일 인덱스).
        Index(
            "uq_reliability_tests_workspace_name",
            "workspace_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        index=True,
    )
    """수행하는 부서. **비울 수 없다** — 전역 신뢰성 시험은 없다. 같은 이름의 시험을
    두 부서가 다른 조건으로 돌리는 것이 보통이고, 그 차이가 이 표의 존재 이유다."""
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text, default="", server_default="")
    """무엇을 확인하는 시험인가. 이름만으로는 「HAST」 가 무엇을 보려는 것인지 옆 부서
    사람은 모른다."""

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """지우지 않는다. 그 시험으로 낸 보고서가 밖에 남아 있다."""


class ReliabilityTestItem(Base):
    """신뢰성 시험이 쓰는 시험 항목 — **장비로 가는 다리.**

    이것이 없으면 「이 시험을 할 장비가 우리 부서에 있나」 를 물을 길이 없다. 비워 둘 수는
    있다(장비 없이 하는 관능 시험) — 그때 화면은 「장비 없음」 이 아니라 「안 정함」 으로
    읽는다.
    """

    __tablename__ = "reliability_test_items"
    __table_args__ = (
        UniqueConstraint(
            "reliability_test_id", "test_item_term_id", name="uq_reliability_test_items_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reliability_test_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reliability_tests.id", ondelete="CASCADE"),
        index=True,
    )
    test_item_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        index=True,
    )
