"""시험법 — 규격이 무엇을 요구하는가.

검색의 사슬에서 가운데 마디다.

    시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
                                  여기

## 왜 시험 항목과 따로 두나

시험 항목(인장)은 **무엇을 재는가**이고 시험법(ASTM E8/E8M-24)은 **어떻게 재는가**
다. 한 항목에 규격이 여럿이고, 규격마다 요구하는 조건이 다르다 — 항목만으로
장비를 고르면 "인장은 되는데 그 규격은 안 되는" 장비가 답에 섞인다.

## 판(edition)을 값에 붙이지 않는다

E8 과 E8M 은 환봉 게이지 길이가 다르고, 판이 바뀌면 요구 조건이 바뀐다. 그것을
이름 문자열에 섞으면 ASTM E8 과 ASTM E8-24 가 별개 값으로 갈린다 — 칸을 따로 둔다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 시험법의 상태.
#:   active     현행
#:   superseded 개정으로 대체됨. **지우지 않는다** — 옛 판으로 잰 데이터가 있다
#:   draft      사내 시험법 초안
METHOD_STATUSES = ("draft", "active", "superseded")


class TestMethod(Base):
    __tablename__ = "test_methods"
    __table_args__ = (
        # 같은 규격의 같은 판이 둘 있으면 어느 쪽 요구 조건이 맞는지 알 수 없다.
        UniqueConstraint("code", "edition", name="uq_test_methods_code_edition"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(100), index=True)
    """규격 번호. ASTM E8/E8M · ISO 6892-1 · KS B 0802."""
    edition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """판. 2024 · 22. **비워 둘 수 있다** — 사내 시험법에는 판이 없다."""
    title: Mapped[str] = mapped_column(String(300))

    test_item_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """어느 시험 항목의 규격인가(기준정보 축 test_item)."""
    body_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """제정 기관(기준정보 축 standard_body). ASTM · ISO · KS · 사내."""

    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("test_methods.id", ondelete="SET NULL"),
        nullable=True,
    )
    """무엇으로 대체됐나. **끊어 두면 옛 판을 보던 사람이 다음 판을 못 찾는다.**"""

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """NULL 이면 전사 공용. 공개 규격은 대개 전사고, 사내 시험법이 부서 것이다.
    **전역은 여러 부서가 함께 쓰므로 시스템 관리자만 고친다.**"""

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class MethodRequirement(Base):
    """이 시험법이 요구하는 조건 하나. 20 kN 이상, 상온에서 300도까지 …

    ## 값은 SI 로 담는다

    사람이 kN 으로 적어도 저장은 N 이다(ConditionKey.si_unit). 검색이 장비 역량과
    직접 비교하려면 둘이 같은 단위여야 하는데, 화면 단위로 담으면 그 비교가 조용히
    틀린다 — 20 이 20 N 인지 20 kN 인지 값만 봐서는 알 수 없다.

    ## 못 지켜도 막지 않는다

    is_mandatory 가 false 인 요구는 권고다. 규격이 숫자를 주지 않고 비율이나 장비
    사양에 위임하는 경우가 흔하고, 그때 막으면 실제로 하고 있는 시험을 등록할 수
    없게 된다 — 그러면 사람은 시스템 밖에서 일한다.
    """

    __tablename__ = "method_requirements"
    __table_args__ = (
        UniqueConstraint("method_id", "condition_key_id", name="uq_method_requirements_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    method_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("test_methods.id", ondelete="CASCADE"), index=True
    )
    condition_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("condition_keys.id", ondelete="RESTRICT"), index=True
    )
    """RESTRICT — 조건 정의를 지우면 이 요구가 무엇을 뜻했는지 알 수 없게 된다.
    쓰는 곳이 있는 조건은 지우는 대신 끈다(ConditionKey.is_active)."""

    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    """**한쪽을 비울 수 있다.** 20 kN 이상은 min 만 있고 max 가 없다 — 0 으로
    채우면 상한이 0 인 것과 구별되지 않는다."""

    text_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """kind 가 choice·boolean 인 조건의 값."""

    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
