"""장비 사양의 **정의** — 그룹·칸·적용 분류.

`ConditionKey`(시험 조건)와 나란한 자리다. 둘 다 "칸의 계약" 이지만 쓰임이 다르다.

    ConditionKey      검색이 묻는 축. 일곱 개. 범위 비교가 되어야 한다
    SpecDefinition    사양서에 적힌 모든 것. 수백 개. 대부분 검색 안 한다

한 표로 합치지 않은 이유: 프레임 강성·외형 치수·통신 속도가 검색 폼에 뜨면 그
화면은 못 쓰게 된다. 대신 **잇는다** — `condition_key_id` 를 채운 사양은 값을 넣는
순간 그 모델의 역량에 반영된다(ADR 0005).

값은 `equipment` 모듈의 `ModelSpecValue` 가 갖는다. 정의가 여기 있는 이유는
기준정보와 같다 — 사람이 고르는 칸의 뜻을 정하는 자리는 한 곳이어야 한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 사양 한 칸이 담는 것.
#:
#:   number   단일 수치.  최대 하중 300 kN
#:   range    구간.       시험 온도 -180 ~ 750 degC
#:   choice   고른 값.    냉각 방식 = LN2 | Intracooler | 없음
#:   boolean  있나 없나.  항온조 내장
#:   text     문장.       "±0.5% of reading down to 1/1000th of load cell capacity"
#:
#: **text 를 두는 이유**: 카탈로그의 정확도 서술은 수치로 못 담는다. 그것을 억지로
#: 숫자 칸에 넣게 하면 사람은 반올림하거나 조건절을 버린다 — 그러면 원문이 사라진다.
SPEC_KINDS = ("number", "range", "choice", "boolean", "text")


class SpecGroup(Base):
    """사양을 묶는 단위. 화면이 이 순서로 접었다 편다.

    분류(카테고리)와 다른 축이다 — 분류는 "어느 장비에 붙나" 이고, 그룹은 "사람이
    어떤 덩어리로 읽나" 다. 성능과 설치 조건은 어느 장비에나 있고, 그 둘은 보는
    사람이 다르다.
    """

    __tablename__ = "spec_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SpecDefinition(Base):
    """사양 한 칸의 계약.

    ## 적용 분류를 비울 수 있다

    비면 **공통**이다 — 전원·외형·무게처럼 분류를 가리지 않는 것들. 채우면 그
    분류의 모델에서만 입력 칸이 뜬다. 화면은 「이 분류에 없는 사양」 을 접어서 함께
    보여 준다: 분류를 잘못 정했다고 사양을 못 적는 상태를 만들지 않는다(ADR 0005).

    ## 검색축과 잇는다

    `condition_key_id` 를 채우면 이 사양의 값이 그 모델의 역량으로 따라 들어간다.
    같은 숫자를 두 번 적지 않게 하는 자리다.
    """

    __tablename__ = "spec_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    """코드가 거는 이름. force_capacity · crosshead_travel."""
    label: Mapped[str] = mapped_column(String(150))
    group_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("spec_groups.id", ondelete="RESTRICT"), index=True
    )

    kind: Mapped[str] = mapped_column(String(10), default="number", server_default="number")
    dimension: Mapped[str] = mapped_column(String(30), default="", server_default="")
    si_unit: Mapped[str] = mapped_column(String(20), default="", server_default="")
    display_unit: Mapped[str] = mapped_column(String(20), default="", server_default="")
    """**저장 단위와 표시 단위를 나눈다.** 조건 정의와 같은 규칙이다 — 실무가 kN 으로
    말하는데 저장만 N 이면 화면마다 환산이 끼고, 그러면 언젠가 한쪽만 고쳐진다."""

    choices: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")

    condition_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("condition_keys.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """검색축과의 연결. 채우면 이 사양의 값이 모델 역량으로 반영된다.

    RESTRICT — 쓰는 사양이 있는 조건은 못 지운다. 지우면 그 사양이 무엇을 뜻했는지
    알 수 없게 된다."""

    reflect_as: Mapped[str] = mapped_column(String(5), default="max", server_default="max")
    """수치 하나가 역량의 어느 끝인가 — `max` 면 천장, `min` 이면 바닥.

    300 kN 최대하중은 "300까지 된다"(max) 이고, 최소 게이지 폭 1 mm 는 "1부터
    된다"(min) 이다. **하나로 정해 두면 절반이 거꾸로 반영된다** — 그리고 거꾸로
    반영된 값은 검색이 조용히 틀린 답을 내는 방식으로만 드러난다.

    kind 가 range 면 안 본다. 그때는 num_min·num_max 가 이미 양끝을 갖는다.
    """

    help: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    """끄면 새 입력에서 안 뜬다. **지우지는 않는다** — 이미 그 사양으로 적힌 값이
    무엇이었는지 알 수 없게 된다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SpecDefinitionCategory(Base):
    """이 사양이 어느 장비 분류에 붙나. **행이 없으면 공통**이다."""

    __tablename__ = "spec_definition_categories"
    __table_args__ = (
        UniqueConstraint(
            "definition_id", "category_term_id", name="uq_spec_definition_category"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("spec_definitions.id", ondelete="CASCADE"), index=True
    )
    category_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("vocabulary_terms.id", ondelete="CASCADE"), index=True
    )
