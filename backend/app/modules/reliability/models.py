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
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReliabilityTest(Base):
    __tablename__ = "reliability_tests"
    __table_args__ = (
        # **이름 유일성은 DB 가 못 건다**(0044). 같은 이름이라도 **적용군이나 규격서가
        # 다르면 별개의 시험**인데, 그 둘은 `attribute_values` 에 있어서 한 표의 유일
        # 인덱스로는 표현이 안 된다. 두 칸을 여기 베껴 두는 길도 있었지만, 베낀 값은
        # 반드시 갈라진다 — 판정은 `services._check_name_free` 한 곳이다.
        Index("ix_reliability_tests_division_name", "division_term_id", "name"),
        CheckConstraint("status IN ('candidate','confirmed')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    division_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        index=True,
    )
    """수행하는 **사업부**. **비울 수 없다** — 전역 신뢰성 시험은 없다.

    부서(팀)가 아니라 사업부인 이유: 같은 시험을 여러 팀이 돌리는데 팀마다 줄을 만들면
    「저 사업부가 무슨 시험을 하나」 가 답이 안 나오고, 이름 유일성도 팀 단위라 막아 주지
    않는다. 누가 넣었는지는 `created_by` 와 감사 기록이 안다."""
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text, default="", server_default="")
    """무엇을 확인하는 시험인가. 이름만으로는 「HAST」 가 무엇을 보려는 것인지 옆 부서
    사람은 모른다."""

    status: Mapped[str] = mapped_column(
        String(12), default="confirmed", server_default="confirmed", index=True
    )
    """`candidate`(후보) · `confirmed`(확정).

    **기계 자격(PAT)으로 들어온 쓰기는 후보가 된다.** 사람이 화면에서 읽고 확인해야
    확정이다 — 자세한 것은 ADR 0009."""
    submitted_via: Mapped[str | None] = mapped_column(String(60), nullable=True)
    """올린 통로 — PAT 이름. `created_by` 는 토큰 **소유자**라 사람과 AI 를 못 가른다."""

    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    """내용을 보고 확인한 사람. **반년 뒤 「이 값 누가 보증했어」 에 답할 자리가 여기다.**"""
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_document_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """이 줄이 속한 **규격서의 판.**

    **판마다 한 벌을 둔다.** 규격서 하나에 시험이 한 벌만 붙었더니, 같은 문서의 개정 14와
    18에 이름이 같은 시험 70개 중 36개가 조건이 다른데도 먼저 올라간 판이 이기고 나머지는
    막혔다(2026-09-30). 신뢰성 시험은 수백 건이고 개정이 잦지 않아 복제의 값이 싸다 —
    그 대신 「이 판의 목록」 이 계산 없이 바로 나온다.

    `introduced_revision_id` 와 다르다: 이 칸은 **지금 어느 판의 것인가**(자리)이고
    그쪽은 **어디서 왔는가**(이력)다. 개정 18의 줄도 「개정 14에서 신설」 일 수 있다."""
    introduced_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_document_revisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    """이 시험이 **신설된 개정.** 「이 시험은 개정 18에서 생겼다」 를 적을 자리다 — 판 글자
    하나로는 못 적었다."""
    reviewed_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_document_revisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """사람이 **마지막으로 확인한 개정.**

    규격서가 개정되어도 딸린 시험은 확정인 채로 둔다 — 수십 건이 한꺼번에 후보로 내려가면
    그날 일이 멈추고, 멈춘 일은 미뤄진다. 대신 이 칸이 최신 개정보다 뒤면 「개정 19 기준으로
    아직 안 본 시험」 으로 서고, 사람이 본 것부터 표가 떨어진다."""

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


class TestItemProposal(Base):
    """시험 항목 축에 **맞는 값이 없을 때** 기계가 남기는 제안.

    시험 항목 축은 closed 다 — 검색의 첫 축이라 오타 하나가 값이 되면 그 뒤로 아무도 못
    찾는다. 그래서 기계가 값을 못 더하는 것은 **옳다.** 그런데 못 더하는 쪽에 **말할 자리도**
    없었다: 스무 건 중 아홉 건이 시험 항목 없이 들어왔고, 왜 비었는지가 아무 데도 안 남아
    검토하는 사람은 그 아홉 건을 「안 적은 것」 과 구별할 수 없었다.

    같은 말이 여러 시험에서 나오면 `normalized` 로 한 줄에 모인다 — 관리자는 스무 번이
    아니라 한 번 판단하고, 정한 것이 그 제안을 낸 시험들에 함께 걸린다.
    """

    __tablename__ = "test_item_proposals"
    __table_args__ = (
        UniqueConstraint(
            "reliability_test_id", "normalized", name="uq_test_item_proposals_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    text: Mapped[str] = mapped_column(String(200))
    """문서에 적힌 그대로 — 「염수분무(5%)」. **고쳐 쓰지 않는다**: 판단하는 사람이 원문을
    봐야 축의 어느 값인지 정할 수 있다."""
    normalized: Mapped[str] = mapped_column(String(200), index=True)
    """같은 말을 모으는 비교키. 띄어쓰기·대소문자를 지운다."""
    reliability_test_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reliability_tests.id", ondelete="CASCADE"),
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """왜 축에서 못 찾았는지 — 「염수 분무는 있는데 농도별 구분이 없음」."""
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    """`open` · `linked`(기존 값에 이었다) · `created`(축에 세웠다) · `rejected`."""
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    """정하고 나서 어느 값이 됐나."""
    submitted_via: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
