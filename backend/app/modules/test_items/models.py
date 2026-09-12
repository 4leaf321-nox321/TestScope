"""시험 항목 — **이 장비로 무엇을 어디까지 할 수 있나.**

    시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
                                              여기

시험 항목은 장비와 시험 항목 사이의 한 행이다. 한 장비가 여러 시험을 하고(만능재료
시험기는 인장도 압축도 한다), 같은 시험이라도 붙인 지그와 챔버에 따라 되는 범위가
다르다 — 그래서 장비에 칸을 늘리는 것으로는 못 담는다.

## 왜 장비에 온도 범위를 안 적나

적으면 그 장비의 온도 범위가 하나가 된다. 그런데 실제로는 **인장 지그로는 200도
까지, 굽힘 지그로는 상온만** 같은 일이 흔하다. 능력은 장비의 성질이 아니라
장비와 시험의 짝에 붙는다.

## 검증 상태를 함께 든다

카탈로그에 적힌 사양과 실제로 해 본 것은 다르다. 사양만 믿고 답하면 "된다고 해서
갔는데 안 되더라" 가 나오고, 그 한 번으로 시스템 전체가 안 믿긴다.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
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

#: 이 시험 항목을 어디까지 믿을 수 있나.
#:   catalog   장비 카탈로그·사양서에 적힌 값. 아직 해 본 적은 없다
#:   verified  실제로 해서 결과를 낸 적이 있다
#:   limited   되기는 하는데 조건이 붙는다(지그 제작 필요 등). note 를 읽어야 한다
CAPABILITY_CONFIDENCES = ("catalog", "verified", "limited")


class EquipmentTestItem(Base):
    __tablename__ = "equipment_test_items"
    __table_args__ = (
        # 같은 장비 + 같은 시험 항목 + 같은 시험법은 한 행이다. 둘이면 어느 쪽
        # 범위가 맞는지 알 수 없고, 검색 결과에 같은 장비가 두 번 뜬다.
        UniqueConstraint(
            "equipment_id",
            "test_item_term_id",
            "method_id",
            name="uq_equipment_test_items_triple",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE"), index=True
    )
    test_item_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        index=True,
    )
    """시험 항목(기준정보 축 test_item). RESTRICT — 쓰는 시험 항목이 있는 항목을 지우면
    그 장비가 무엇을 할 수 있었는지 알 수 없게 된다."""

    method_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("test_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """어느 규격까지 되는가. **비워 둘 수 있다** — 규격을 특정하지 않고 "인장은
    된다" 만 아는 단계가 실제로 있고, 그것도 검색에는 쓸모가 있다."""

    confidence: Mapped[str] = mapped_column(
        String(20), default="catalog", server_default="catalog", index=True
    )
    verified_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    """마지막으로 실제 확인한 날. confidence 가 verified 인데 이 값이 3년 전이면
    화면이 그것을 말해 줘야 한다 — 지그도 챔버도 그동안 바뀐다."""

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """조건이 붙는다면 그 조건. 지그 제작 2주 소요 같은 것. **검색 결과에 그대로
    실린다** — 여기 적힌 것을 안 보여 주면 limited 와 verified 가 같아 보인다."""

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EquipmentTestCondition(Base):
    """이 시험 항목의 조건 하나가 어디까지 되나. 하중 0~50 kN, 온도 -70~300 도.

    ## 표를 나눈 이유

    JSONB 한 칸에 넣으면 검색이 "80도가 이 장비의 온도 구간 안에 드나" 를 SQL 로
    물을 수 없다. 인덱스도 못 탄다. 조건 수는 장비당 서넛이라 표가 커질 걱정은 없다.

    ## 값은 SI 로 담는다

    MethodRequirement 와 **같은 단위여야** 요구와 시험 항목을 직접 비교할 수 있다.
    한쪽만 화면 단위면 그 비교는 조용히 세 자릿수 틀린다.
    """

    __tablename__ = "equipment_test_conditions"
    __table_args__ = (
        UniqueConstraint(
            "equipment_test_item_id",
            "condition_key_id",
            name="uq_equipment_test_conditions_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    equipment_test_item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("equipment_test_items.id", ondelete="CASCADE"),
        index=True,
    )
    condition_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("condition_keys.id", ondelete="RESTRICT"), index=True
    )

    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    """**한쪽을 비울 수 있고, 그것은 "제한 없음" 이다.** 0 으로 채우면 하한이 0 인
    장비와 구별되지 않는다 — 검색이 그 차이로 갈린다."""

    text_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """kind 가 choice·boolean 인 조건의 값."""

    requires_accessory: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    """**본체가 아니라 옵션 부속(챔버·노·클램프)이 있어야 나오는 값.** 카탈로그가
    「-180~320 °C」 를 항온조 옵션 기준으로 적는 일이 흔한데, 그것을 본체 값처럼 두면
    검색이 갖고 있지도 않은 챔버를 전제로 「80 °C 됨」 이라고 답한다 — ADR 0003 이
    막으려던 바로 그 오답. 표시는 남기고 판정을 가른다."""

    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SeriesTestItem(Base):
    """카탈로그 시험 항목 — **사양서가 말하는 것. 계열에 붙는다.**

    보유 장비의 시험 항목과 모양이 같지만 뜻이 다르다. 이쪽은 "이 계열을 사면 무엇이
    되나" 이고, 저쪽은 "우리 3동 201호의 그 대가 지금 무엇을 하나" 다.

    ## 왜 모델이 아니라 계열인가

    제조사 카탈로그의 `models[]` 안에는 시험 항목이 없다 — **무슨 시험이 되나는
    계열의 성질**이다. 갈리는 것은 조건 수치뿐이고, 그것은 모델의 사양이 갖는다.
    모델마다 붙이면 같은 목록을 510번 적게 되고, 510벌은 반드시 갈린다(ADR 0006).

    ## 상속하지 않고 복사한다

    보유 장비를 등록하면서 모델을 고르면, 그 모델이 속한 계열의 시험 항목이 개체로
    **복사되고**(`confidence='catalog'`) **조건은 그 모델의 사양에서 온다.**
    그 뒤로는 개체가 진실이다 — 챔버를 뗀 대, 지그가 없어
    굽힘이 안 되는 대가 실제로 있고, **갈라지는 것이 정상**이기 때문이다.

    상속으로 두면 검색이 "개체 값인가 모델 값인가" 를 매번 되짚어야 하고, 그 되짚기를
    한 화면에서 빠뜨리면 결과가 조용히 갈린다(ADR 0004).
    """

    __tablename__ = "series_test_items"
    __table_args__ = (
        UniqueConstraint(
            "series_id", "test_item_term_id", "method_id", name="uq_series_test_items_triple"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment_series.id", ondelete="CASCADE"), index=True
    )
    test_item_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        index=True,
    )
    method_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("test_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """사양서가 규격까지 명시하면 건다. 대개는 비어 있다 — 카탈로그는 "인장 300 kN"
    까지만 말하고, 어느 규격으로 돌릴지는 쓰는 곳이 정한다."""

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """사양서의 단서. 복사될 때 개체로 함께 간다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SeriesTestItemMethod(Base):
    """이 계열의 시험 항목이 **인용하는 규격** 하나.

    ## 왜 시험 항목을 쪼개지 않고 옆 표로 두나

    카탈로그의 규격 목록은 계열에 평평하게 붙어 온다 — 인장 하나에 ASTM D638 · ISO 527 ·
    ASTM E8 이 함께 걸린다. 시험 항목을 규격마다 쪼개면 **검색이 같은 장비를 여덟 줄로
    답한다**(실측). 그래서 「이 계열은 인장이 된다」 는 한 줄로 두고, 규격은 여기 단다.

    ## 왜 비고 문자열이면 안 되나

    전에는 `note` 에 「카탈로그 인용 규격: ASTM D638 · ISO 527」 로 적었다. 그러면
    453건의 시험법이 **아무것도 가리키지 않는 목록**으로 남는다 — 「ASTM D638 되는
    장비」 를 물으면 문자열을 훑는 수밖에 없고, 판(edition)이 바뀌어도 따라오지 않는다.

    검색 사슬의 세 번째 칸이 여기다: 시험 항목 -> 요구 조건 -> **시험법** -> 가능한 장비.
    """

    __tablename__ = "series_test_item_methods"
    __table_args__ = (
        UniqueConstraint(
            "series_test_item_id", "method_id", name="uq_series_test_item_methods"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_test_item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("series_test_items.id", ondelete="CASCADE"),
        index=True,
    )
    method_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("test_methods.id", ondelete="CASCADE"), index=True
    )
    """CASCADE — 시험법을 지우면 그 인용도 사라진다. 인용은 **그 규격에 딸린 사실**이라
    규격 없이 혼자 남을 이유가 없다(시험 조건과 다르다)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TestItemConditionKey(Base):
    """시험 항목마다 **뜻이 있는 조건 축** — 인장은 하중·속도·온도, 챔버는 온도·습도.

    전에는 어디에도 없었다. 검색은 시험 항목을 골라도 조건 칸에 축 일곱 개를 다 보여
    줬고, 「이 분류의 기종엔 이 사양이 있어야 한다」 를 말할 근거도 없었다 — 검색축
    사양이 있는 기종이 879 중 433 인 이유의 절반이 여기다.

    사람이 정한다(시스템 관리자). 반입은 안 건드린다 — 카탈로그는 이 지식을 안 갖고 있다.
    """

    __tablename__ = "test_item_condition_keys"
    __table_args__ = (
        UniqueConstraint(
            "test_item_term_id", "condition_key_id", name="uq_test_item_condition_keys"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_item_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="CASCADE"),
        index=True,
    )
    condition_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("condition_keys.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SeriesPendingMethod(Base):
    """계열이 인용했는데 **어느 시험 항목의 규격인지 아직 모르는** 것.

    카탈로그 객체의 규격 목록은 계열에 평평하게 붙어 온다. 만능시험기가 ASTM D638 · ISO 178 ·
    ASTM E8 을 함께 인용하면 그중 무엇이 굽힘의 것인지 반입은 모른다 — 시험이 하나뿐인
    계열은 소거로 알지만, 여럿이면 사람이 정해야 한다.

    전에는 그 사이 **누가 인용했나가 DB 어디에도 없었다.** 규격 행은 생기고 링크는 안 생겨,
    시험법 464 중 287 이 「가능 장비 없음」 으로 서 있었다 — 못 하는 시험이 아니라 끊긴
    연결인데 화면이 그 둘을 구별하지 못했다.

    여기 남겨 두면 시험 항목이 정해지는 순간(화면에서든 반입에서든) 그 계열의 그 시험
    항목에 자동으로 붙는다(`methods.services.promote_pending`). 붙고 나면 이 줄은 지운다.
    """

    __tablename__ = "series_pending_methods"
    __table_args__ = (
        UniqueConstraint("series_id", "method_id", name="uq_series_pending_methods"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment_series.id", ondelete="CASCADE"), index=True
    )
    method_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("test_methods.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SeriesTestCondition(Base):
    """계열의 시험 항목의 조건 범위 — **계열 전체가 만족하는 것만.**

    모델마다 갈리는 수치는 여기 안 온다. 여기 적는 것은 「이 계열은 상온 전용」
    처럼 계열 전부에 참인 것과, 사양 칸으로 안 잡히는 것이다. 모델별 조건은
    보유 장비를 만들 때 그 모델의 사양에서 계산된다(ADR 0006).

    JSONB 한 칸으로 두지 않는 이유: 조건 정의의 RESTRICT 와 쓰임 수가 무력해진다.
    쓰는 곳이 있는 조건을 지울 수 있게 되고, 그러면 그 모델이 무엇을 할 수 있었는지
    알 수 없게 된다.
    """

    __tablename__ = "series_test_conditions"
    __table_args__ = (
        UniqueConstraint(
            "series_test_item_id", "condition_key_id", name="uq_series_test_conditions_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_test_item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("series_test_items.id", ondelete="CASCADE"),
        index=True,
    )
    condition_key_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("condition_keys.id", ondelete="RESTRICT"), index=True
    )

    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    """**한쪽을 비울 수 있고, 그것은 "제한 없음" 이다.** 개체 쪽과 같은 규칙이다."""

    text_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requires_accessory: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    """**본체가 아니라 옵션 부속(챔버·노·클램프)이 있어야 나오는 값.** 카탈로그가
    「-180~320 °C」 를 항온조 옵션 기준으로 적는 일이 흔한데, 그것을 본체 값처럼 두면
    검색이 갖고 있지도 않은 챔버를 전제로 「80 °C 됨」 이라고 답한다 — ADR 0003 이
    막으려던 바로 그 오답. 표시는 남기고 판정을 가른다."""
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
