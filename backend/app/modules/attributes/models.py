"""항목 정의와 값 — **칸을 미리 만들지 않고, 이름을 데이터로 둔다.**

신뢰성 시험에 무슨 칸이 붙어야 하는지는 조사 중이다. 조건·판정 기준·근거 규격·시료 수 …
후보는 많고 표준은 아직 없다. 그렇다고 열(column)을 미리 뚫으면 안 쓰는 열이 남고, 이름을
바꾸려면 마이그레이션이 필요하고, 두 사람이 각각 열을 더하면 갈린다. 그래서 항목의 이름과
종류를 **행**으로 두고, 값이 그 행을 가리킨다 — 기종 사양(`SpecDefinition` · `ModelSpecValue`)
과 같은 얼개다.

## 초안과 정식

    draft     누가 「새 항목」 으로 적으면 자동으로 생긴다. 종류·단위는 있지만 온톨로지 밖이다.
    standard  시스템 관리자가 확정한 것. 필수 표시·검색축 연결·의미 색인에 들어간다.

초안은 **표시와 수집만** 한다 — 검색 판정·resolve·의미 색인·MCP 의 구조 응답에는 정식만
들어간다. 온톨로지로 들어가는 문은 「정식으로 올리기」 하나다. 그래야 초안이 아무리 쌓여도
검색 품질이 흔들리지 않는다.

이름이 갈리는 것(온도 · 시험온도 · Temp)은 입력 칸이 기존 정의를 먼저 보여 줘서 줄이고,
그래도 갈린 것은 `merge_into` 로 합친다 — 값의 `definition_id` 만 바뀌고 원래 행은 꺼진다.

## 값은 종류별로 칸을 나눈다

`300` 과 `약 300` 과 `300 kN` 이 한 문자열 칸에 섞이면 비교가 성립하지 않는다(기종 사양과
같은 규칙). 단위는 **값에** 남긴다 — 초안은 사람마다 단위가 다를 수 있고, 정식으로 올릴 때
정의의 단위로 환산해 읽으면 된다. 환산은 읽을 때 하고 저장값은 적힌 그대로 둔다.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 속성이 붙는 대상. **모든 객체 종류에 관리자가 칸을 더할 수 있어야 한다** — 기준정보 허브가
#: 그것을 한 표로 보여 준다. 새 대상은 여기와 AttributeValue 의 열, services._TARGET_COLUMN,
#: 그 대상의 Out/Update 에 한 줄씩.
ATTRIBUTE_TARGETS = ("reliability_test", "equipment", "series", "method")

#: 항목 한 칸이 담는 것.
#:
#:   number     단일 수치 + 단위.        시료 수 5 · 인가 전압 12 V
#:   range      구간 + 단위.             온도 -40 ~ 125 degC
#:   text       문장.                    판정 기준 「외관 이상 없음」
#:   boolean    있나 없나.               전처리 필요
#:   date       날짜.                    제정일
#:   choice     정의가 준 선택지 중 하나. 시료 형태 = 시편 | 완제품
#:   condition  검색 조건 축의 값.       정의의 condition_key_id 가 축, 값은 range 와 같은 칸
#:   term       기준정보 축의 값 참조.   정의의 vocabulary_id 가 축, 값은 term_id
#:   method     규격 참조.               값은 ref_method_id
#:
#: condition 을 range 와 따로 두는 이유: 같은 물리량을 검색 조건 축과 **같은 축·같은 차원**
#: 으로 적어야 나중에 「이 절차를 돌릴 수 있는 장비」 판정이 성립한다. 문장으로 받으면 그
#: 길이 막힌다.
ATTRIBUTE_KINDS = (
    "number",
    "range",
    "text",
    "boolean",
    "date",
    "choice",
    "condition",
    "term",
    "method",
)
ATTRIBUTE_STATUSES = ("draft", "standard")


class AttributeDefinition(Base):
    """항목 하나의 계약 — 이름·종류·단위, 그리고 초안인지 정식인지."""

    __tablename__ = "attribute_definitions"
    __table_args__ = (
        # 같은 대상에 같은 이름은 하나 — 꺼진 것(합쳐진 것)은 빼고. 대소문자 무시는
        # 서비스가 한다(신뢰성 시험 이름과 같은 규칙).
        Index(
            "uq_attribute_definitions_target_label",
            "target",
            "label",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        CheckConstraint(
            "target IN ('reliability_test','equipment','series','method')",
            name="target",
        ),
        CheckConstraint("status IN ('draft','standard')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target: Mapped[str] = mapped_column(String(20), index=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    """코드가 거는 이름. 초안은 `draft-<8자>` 로 자동, 정식으로 올릴 때 사람이 바꿀 수 있다."""
    label: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(10), default="text", server_default="text")
    unit: Mapped[str] = mapped_column(String(20), default="", server_default="")
    """정식 항목의 **읽는 단위**. 값은 적힌 단위를 갖고 있고, 화면은 이 단위로 환산해 나란히
    보여 준다. 초안은 비어 있어도 된다."""
    choices: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")

    condition_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("condition_keys.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """kind=condition 의 축. 채우면 이 항목의 값이 그 축의 조건으로 읽힌다."""
    vocabulary_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabularies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    """kind=term 의 축 — 어느 기준정보 축의 값을 고르나."""

    status: Mapped[str] = mapped_column(String(10), default="draft", server_default="draft")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    """정식 항목만 뜻이 있다. 등록 화면이 비어 있으면 표시한다 — **막지는 않는다.** 필수라고
    막으면 사람은 아무 값이나 넣는다."""
    help: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    """끄면 새 입력에서 안 뜬다. 지우지 않는다 — 그 항목으로 적힌 값이 무엇이었는지 남아야
    한다."""
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("attribute_definitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    """합쳐진 초안이 어디로 갔나. 「그 항목 어디 갔어」 의 답."""

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AttributeValue(Base):
    """대상 하나에 붙은 항목 값 하나. 대상은 둘 중 하나만 채운다.

    비어 있는 수치 칸은 「제한 없음」 이다(ADR 0003) — 0 으로 채우면 하한이 0 인 것과 구별이
    안 된다.
    """

    __tablename__ = "attribute_values"
    __table_args__ = (
        CheckConstraint(
            "(reliability_test_id IS NOT NULL)::int + (equipment_id IS NOT NULL)::int"
            " + (series_id IS NOT NULL)::int + (method_id IS NOT NULL)::int = 1",
            name="one_target",
        ),
        Index(
            "uq_attribute_values_reliability",
            "reliability_test_id",
            "definition_id",
            unique=True,
            postgresql_where=text("reliability_test_id IS NOT NULL"),
        ),
        Index(
            "uq_attribute_values_equipment",
            "equipment_id",
            "definition_id",
            unique=True,
            postgresql_where=text("equipment_id IS NOT NULL"),
        ),
        Index(
            "uq_attribute_values_series",
            "series_id",
            "definition_id",
            unique=True,
            postgresql_where=text("series_id IS NOT NULL"),
        ),
        Index(
            "uq_attribute_values_method",
            "method_id",
            "definition_id",
            unique=True,
            postgresql_where=text("method_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    reliability_test_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reliability_tests.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("equipment_series.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    method_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("test_methods.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    """규격 속성의 대상. 값의 `method_id`(kind=method 참조)와는 다른 열 — 하나는 「어느 규격에
    붙은 값인가」, 하나는 「값이 가리키는 규격」 이다."""

    num_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="", server_default="")
    """적힌 그대로의 단위. 정의의 단위와 달라도 된다 — 읽을 때 환산한다."""
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    bool_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    date_value: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ref_method_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("test_methods.id", ondelete="RESTRICT"),
        nullable=True,
    )
    """kind=method 값이 가리키는 규격. 대상 열 `method_id`(이 값이 붙은 규격)와 다르다."""
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """수치로 못 담는 단서. 「챔버 장착 시」 「시료 5개 기준」."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
