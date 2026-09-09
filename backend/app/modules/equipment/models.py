"""장비 카탈로그와 보유 장비 — **무엇이 있고, 우리 것은 어디에 있나.**

    EquipmentSeries  제품군. 무슨 시험이 되나 · 어느 부속이 붙나 · 누가 만들었나
    EquipmentModel   그 안의 한 기종. **수치가 여기서 갈린다**
    Equipment        보유 장비. 자산번호·자리·상태. 모델의 인스턴스

## 왜 시리즈와 모델을 나누나

제조사 카탈로그 137건을 세어 보니 **한 시리즈 안에서 하중 용량이 중앙값 60배,
최대 1200배 갈렸다**(MTS Criterion 40 은 1~1200 kN, Instron 5900 은 0.5~600 kN).
시리즈를 카탈로그 한 줄로 두면 0.5 kN 짜리 한 대를 가진 부서가 「300 kN 인장
되나요」 에 된다고 답한다 — ADR 0003 이 막으려던 바로 그 오답이다.

반대로 모델만 두면 시리즈에만 있는 것을 510번 반복해 적게 된다. 시험 항목은
`models[]` 에 없다 — **무슨 시험이 되나는 시리즈의 성질**이고, 어디까지 되나가
모델에서 갈린다(ADR 0006).

## 상태를 불리언으로 두지 않는다

가동/비가동으로 나누면 "점검 중" 과 "고장" 과 "폐기" 가 한 칸에 들어간다. 셋은
사람이 할 일이 다르다 — 점검은 기다리면 되고, 고장은 다른 장비를 찾아야 하고,
폐기는 목록에서 빼야 한다.

## 지우지 않는다

deleted_at 만 채운다. 폐기한 장비로 잰 데이터가 밖에 남아 있고, 그것이 어느
장비였는지는 몇 년 뒤에도 물어질 수 있다.
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
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 장비 상태.
#:   operational  가동 — 지금 시험할 수 있다
#:   maintenance  점검·교정 중 — 곧 돌아온다
#:   repair       고장 — 언제 돌아올지 모른다
#:   retired      폐기 — 목록에서 빠지되 기록은 남는다
EQUIPMENT_STATUSES = ("operational", "maintenance", "repair", "retired")

#: 검색이 기본으로 "쓸 수 있다" 로 세는 상태. 점검 중은 뺀다 — 오늘 시험을 잡을
#: 수 없는 장비를 가능하다고 답하면, 그 답을 믿고 일정을 짠 사람이 막힌다.
AVAILABLE_STATUSES = ("operational",)

#: 카탈로그 항목의 상태.
#:   active        파는 것 / 쓰는 것
#:   discontinued  단종. **지우지 않는다** — 우리가 그것을 아직 쓰고 있다
MODEL_STATUSES = ("active", "discontinued")


#: 시리즈가 무엇인가. 부속도 제조사 카탈로그에 실려 오므로 같은 표에 담는다 —
#: 챔버 하나에도 온도 범위와 사양표와 출처가 붙고, 그것을 담을 자리는 여기뿐이다.
SERIES_KINDS = ("main", "accessory", "sensor", "software")

#: 시리즈끼리의 관계. 원본 카탈로그가 쓰는 이름을 그대로 둔다 — 번역하면 반입할
#: 때마다 사전을 한 벌 더 들고 다녀야 하고, 그 사전은 반드시 원본과 갈린다.
#:
#: `extends_temperature` 가 특히 중요하다. 챔버를 달면 시험 온도가 -150~600 으로
#: **바뀐다** — 지금은 그 사실이 비고에만 있고, 검색은 그것을 모른다.
SERIES_RELATIONS = (
    "compatible_accessory",
    "fits_on",
    "requires",
    "controlled_by",
    "extends_temperature",
    "simulates_environment",
    "successor_of",
    "same_family_as",
    "variant_of",
)


class EquipmentSeries(Base):
    """제품군 한 줄 — **제조사가 파는 계열.**

    ## 무엇이 여기 붙나

    무슨 시험이 되나(`ModelCapability`), 어느 부속이 붙나(`SeriesRelation`),
    누가 만들었나, 어느 분류인가. **수치는 안 붙는다** — 그것은 모델에서 갈린다.

    ## 모든 모델은 시리즈에 속한다

    단품이면 모델 하나짜리 시리즈다. 규칙에 예외를 두면 화면이 매번 "시리즈가
    있나 없나" 를 갈라야 하고, 그 갈래를 한 곳에서 빠뜨리면 그 모델은 조용히
    목록에서 사라진다.
    """

    __tablename__ = "equipment_series"
    __table_args__ = (
        UniqueConstraint("maker_term_id", "normalized", name="uq_equipment_series_maker_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    maker_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """제조사(기준정보 축 manufacturer).

    **비울 수 있다.** 자작 장비에는 제조사가 없다 — 그때 막으면 사람은 「사내」 같은
    가짜 값을 만들어 넣고, 그 값이 목록에서 진짜 제조사들 사이에 선다."""

    name: Mapped[str] = mapped_column(String(200))
    """계열 이름. `6800 Series Universal Testing Systems`."""
    name_ko: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """한글 이름. **검색이 이것으로도 걸려야 한다** — 사람은 「인스트론 6800」 으로
    찾지 `6800 Series Universal Testing Systems` 로 찾지 않는다."""
    normalized: Mapped[str] = mapped_column(String(200), index=True)
    """비교키(shared.text.compare_key). 유일성이 이걸로 돈다."""

    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """제조사 안의 브랜드. Instron 의 CEAST, Buehler 의 Wilson.

    제조사와 다른 축이다 — 사람은 「윌슨 경도계」 라고 부르는데 제조사 축에는
    Buehler 로 서 있다. 한 칸에 섞으면 둘 중 하나로만 찾힌다."""

    category_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """장비 분류(기준정보 축 equipment_category). 트리라 상위 분류는 term 의 부모다."""

    kind: Mapped[str] = mapped_column(
        String(20), default="main", server_default="main", index=True
    )
    """본체인가 부속인가. 목록은 기본으로 본체만 보여 준다 — 챔버와 시험기가 한
    줄씩 섞여 서면 「우리가 무슨 장비를 가졌나」 가 안 보인다."""

    drive: Mapped[str] = mapped_column(String(30), default="", server_default="")
    """구동 방식. 같은 하중이라도 구동이 다르면 할 수 있는 시험이 다르다."""
    form_factor: Mapped[str] = mapped_column(String(40), default="", server_default="")

    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    """한 줄 설명. 목록에서 계열을 가려내는 근거가 된다."""
    spec_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """사양으로 못 담는 것 — 옵션 목록·특징 문장 같은 것."""

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """대표 출처 문서. 값마다 붙는 출처와 별개로, **이 계열을 어디서 봤나**에 답한다."""

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class SeriesRelation(Base):
    """계열끼리의 관계 — **무엇을 달 수 있고, 무엇의 후속인가.**

    부속을 별도 표로 두지 않은 이유: 부속도 계열이다. 챔버에도 모델이 여럿이고
    온도 범위가 갈린다. 관계만 따로 두면 그 둘이 한 자리에서 이어진다.
    """

    __tablename__ = "series_relations"
    __table_args__ = (
        UniqueConstraint(
            "host_series_id", "part_series_id", "relation", name="uq_series_relations_triple"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    host_series_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment_series.id", ondelete="CASCADE"), index=True
    )
    part_series_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment_series.id", ondelete="CASCADE"), index=True
    )
    relation: Mapped[str] = mapped_column(String(30), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """관계에 붙는 단서. `-150 ~ +600 °C` 처럼 **무엇이 어떻게 바뀌는지**가 여기 온다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EquipmentModel(Base):
    """계열 안의 한 기종 — **수치가 여기서 갈린다.**

    68SC-05 와 68FM-300 은 같은 6800 시리즈지만 하중이 0.5 kN 과 300 kN 이다.
    제조사·분류·시험 항목은 시리즈가 갖고, 여기에는 **그 기종만의 것**이 온다:
    사양값(`ModelSpecValue`)·형태·무게.

    ## 보유 장비가 가리키는 것은 모델이다

    시리즈를 가리키게 두면 검색이 답할 수 없다 — 「300 kN 됩니까」 에 시리즈는
    「0.5~300 kN 입니다」 라고밖에 못 하고, 그 대답은 우리가 가진 그 한 대에 대해
    아무것도 말하지 않는다(ADR 0006).

    ## 전사 공용이다

    한 부서가 고치면 다른 부서가 가리키던 모델의 뜻이 바뀐다 — 그래서 시스템
    관리자만 손댄다(`owner_workspace_id` 를 두지 않는 이유이기도 하다).
    """

    __tablename__ = "equipment_models"
    __table_args__ = (
        # 한 계열에 같은 기종명이 둘 있으면 어느 쪽을 가리켰는지 알 수 없다.
        UniqueConstraint("series_id", "normalized", name="uq_equipment_models_series_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("equipment_series.id", ondelete="RESTRICT"),
        index=True,
    )
    """속한 계열. **비울 수 없다** — 단품이면 모델 하나짜리 계열을 만든다.
    예외를 두면 화면이 매번 갈래를 타야 하고, 한 곳에서 빠뜨리면 그 모델이
    조용히 목록에서 사라진다.

    RESTRICT — 기종이 매달린 계열은 못 지운다."""

    name: Mapped[str] = mapped_column(String(150))
    """기종명. `68FM-300` · `HIT450P`. **계열 이름은 여기 안 적는다** — 위 칸이 갖는다."""
    name_ko: Mapped[str | None] = mapped_column(String(150), nullable=True)
    normalized: Mapped[str] = mapped_column(String(150), index=True)
    """비교키(shared.text.compare_key). 유일성이 이걸로 돈다 — `5982` 와 `5982 ` 는
    눈에 같아 보이는데 DB 는 다르게 본다."""

    form_factor: Mapped[str] = mapped_column(String(40), default="", server_default="")
    """탁상형·플로어형처럼 생김새. 같은 계열 안에서 갈리므로 계열이 아니라 여기 있다."""

    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    """**계열과 따로 둔다.** 계열은 살아 있는데 그중 한 기종만 단종되는 일이 흔하다."""
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """사양으로 못 담는 것 중 이 기종만의 단서."""

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    """자산번호. **사람이 현장에서 부르는 이름이자 유일 키다** — 라벨에 붙어 있고,
    다른 시스템과 대조할 때도 이것으로 맞춘다."""
    name: Mapped[str] = mapped_column(String(200))

    model_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("equipment_models.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """카탈로그의 어느 모델인가. **제조사·분류·모델명은 그쪽이 갖는다.**

    **비울 수 있다.** 자작 장비나 아직 카탈로그에 없는 것이 실제로 있고, 그때 등록을
    막으면 사람은 시스템 밖에서 일한다. 대신 목록이 「카탈로그 미연결」 로 표시한다 —
    빈 칸을 빈 칸으로 두면 아무도 안 채운다(ADR 0004).

    RESTRICT: 가리키는 장비가 있는 모델은 못 지운다. 지우면 그 장비가 무엇이었는지
    알 수 없게 된다 — 단종은 지우는 것이 아니라 status 로 적는다."""

    serial_no: Mapped[str | None] = mapped_column(String(100), nullable=True)

    owner_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """보유 부서. NULL 이면 전사 공용 장비 — 시스템 관리자만 만들고 고친다.

    RESTRICT 인 이유: 부서를 지우면서 장비가 함께 사라지면, 그 장비로 잰 데이터가
    가리킬 곳을 잃는다. 부서는 지우는 것이 아니라 보관하거나 합친다."""

    site_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """거점(기준정보 축 site). 공장·연구소처럼 **가려면 이동해야 하는 단위**."""
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """거점 안의 자리. 3동 201호. 자유 문자열로 둔다 — 이것까지 축으로 만들면
    호실 하나 바뀔 때마다 기준정보를 고쳐야 한다."""

    status: Mapped[str] = mapped_column(
        String(20), default="operational", server_default="operational", index=True
    )
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    contact_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    """담당자. **찾은 다음에 연락할 사람이 없으면 검색은 절반만 한 것이다.**"""

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

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


class EquipmentCalibration(Base):
    """교정 이력.

    **역량과 별개의 칸이다.** 장비가 20 kN 을 낼 수 있다는 것과 그 값이 지금 믿을
    만하다는 것은 다른 이야기다. 교정이 만료된 장비도 목록에는 남되, 검색 결과가
    그 사실을 말해 줘야 한다 — 말 안 하면 사람은 만료된 장비로 시험을 잡는다.
    """

    __tablename__ = "equipment_calibrations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE"), index=True
    )
    calibrated_on: Mapped[date] = mapped_column(Date, index=True)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    """다음 교정 예정일. 홈 화면의 "곧 만료" 목록이 이것을 본다."""
    certificate_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SpecSource(Base):
    """사양을 옮겨 적은 원본 문서 — **어디서 나온 값이냐에 답하는 자리.**

    421개 카탈로그에서 손으로 옮기는 일이다. 출처가 없으면 반년 뒤 "이 300 kN 어디서
    나왔냐" 를 아무도 답할 수 없고, 카탈로그가 개정돼도 **무엇을 다시 봐야 하는지**
    모른다(ADR 0005).

    `sha256` 을 두는 이유: 같은 이름으로 새 판이 들어오는 일이 흔하다. 해시가 바뀌면
    그 문서에서 온 값을 다시 볼 대상으로 잡을 수 있다.
    """

    __tablename__ = "spec_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    path: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    """`source/` 안의 상대 경로. `instron/6800-series-floor-model-utm.pdf`"""
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    maker_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    """카탈로그가 찍힌 날. 같은 모델의 두 판 중 어느 것이 새 것인지 가른다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelSpecValue(Base):
    """모델이 실제로 갖는 사양값 하나.

    ## 칸을 나눠 둔 이유

    `kind` 에 따라 채우는 칸이 다르다 — 수치는 `num_value`, 구간은 `num_min`/`num_max`,
    고른 값과 문장은 `text_value`, 참거짓은 `bool_value`. 한 칸에 문자열로 다 담으면
    `300` 과 `약 300` 과 `300 kN` 이 섞이고, 그때 비교가 성립하지 않는다.

    ## 비어 있는 쪽은 "제한 없음" 이다

    조건 범위와 같은 규칙이다(ADR 0003). 0 으로 채우면 하한이 0 인 것과 구별되지 않는다.
    """

    __tablename__ = "model_spec_values"
    __table_args__ = (
        UniqueConstraint("model_id", "definition_id", name="uq_model_spec_values_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment_models.id", ondelete="CASCADE"), index=True
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    """RESTRICT — 쓰는 값이 있는 정의는 못 지운다. 지우면 그 숫자가 무엇이었는지 알
    수 없게 된다. 안 쓰려면 정의를 끈다(`is_active`)."""

    num_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    bool_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """수치로 못 담는 단서. `1 & 3 Phase 에 따라 다름` · `챔버 장착 시` 같은 것.

    **카탈로그가 조건을 달아 적는 일이 흔하다.** 그것을 버리면 값만 남고 그 값이
    언제 성립하는지가 사라진다."""

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
