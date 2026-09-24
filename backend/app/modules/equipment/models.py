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
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 장비 상태.
#:   incoming     입고 — 들어왔지만 아직 자리에 안 앉았다
#:   operational  가동 — 지금 시험할 수 있다
#:   idle         유휴 — 쓸 수 있는데 안 쓰고 있다
#:   maintenance  점검·교정 중 — 곧 돌아온다
#:   repair       고장 — 언제 돌아올지 모른다
#:   retired      폐기 — 목록에서 빠지되 기록은 남는다
#:
#: **유휴를 고장과 한 칸에 두지 않는다.** 「안 쓰고 있다」 와 「못 쓴다」 는 빌리려는
#: 사람에게 정반대다 — 유휴는 오히려 빌리기 가장 쉬운 장비다.
EQUIPMENT_STATUSES = (
    "incoming",
    "operational",
    "idle",
    "maintenance",
    "repair",
    "retired",
)

#: 검색이 "쓸 수 있다" 로 세는 상태.
#:
#: **유휴가 들어간다** — 안 쓰고 있다는 것은 못 쓴다는 뜻이 아니다. 입고는 뺀다:
#: 아직 자리에 안 앉은 장비를 가능하다고 답하면, 그 답을 믿고 일정을 짠 사람이
#: 막힌다. 점검·수리·폐기도 같은 이유로 뺀다.
AVAILABLE_STATUSES = ("operational", "idle")

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

    무슨 시험이 되나(`SeriesTestItem`), 어느 부속이 붙나(`SeriesRelation`),
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
    """제조사(온톨로지 축 manufacturer).

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
    """장비 분류(온톨로지 축 equipment_category). 트리라 상위 분류는 term 의 부모다."""

    kind: Mapped[str] = mapped_column(
        String(20), default="main", server_default="main", index=True
    )
    """본체인가 부속인가. 목록은 기본으로 본체만 보여 준다 — 챔버와 시험기가 한
    줄씩 섞여 서면 「우리가 무슨 장비를 가졌나」 가 안 보인다."""

    drive_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """구동 방식(온톨로지 축 `drive`) — 전기기계식·유압식·진자식.

    **무엇으로 힘을 내나는 무엇을 할 수 있나와 곧장 이어진다.** 유압은 큰 하중을,
    전기동력은 높은 주파수를, 진자는 충격을 낸다 — 고르는 사람이 실제로 묻는 축이라
    자유 문자열로 두면 안 된다."""
    """구동 방식. 같은 하중이라도 구동이 다르면 할 수 있는 시험이 다르다."""
    form_factor_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """형태(온톨로지 축 `form_factor`) — 탁상형·바닥형·휴대형.

    **자유 문자열이 아니라 축이다.** 원본이 `benchtop` 으로 적어 오는 것을 그대로 두면
    화면에 영어가 뜨고, 「탁상형만」 으로 거를 수도 없다. 값의 `code` 에 원본 슬러그가
    남아 있어 반입이 그것으로 찾는다.

    RESTRICT — 쓰는 기종이 있는 형태는 못 지운다."""

    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    """한 줄 설명. 목록에서 계열을 가려내는 근거가 된다."""
    spec_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """사양으로 못 담는 것 — 옵션 목록·특징 문장 같은 것."""

    raw_limits: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    """계열 사양표(`limits`) 원문 그대로.

    기종이 여럿인 계열에서 이 값은 **봉투**다 — 0.5~300 kN 은 어느 기종의 값도
    아니라 수치로 안 들인다(ADR 0006). 그래도 사람이 읽을 값이라 원문을 남긴다."""

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

    form_factor_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """형태(온톨로지 축 `form_factor`) — 탁상형·바닥형·휴대형.

    **자유 문자열이 아니라 축이다.** 원본이 `benchtop` 으로 적어 오는 것을 그대로 두면
    화면에 영어가 뜨고, 「탁상형만」 으로 거를 수도 없다. 값의 `code` 에 원본 슬러그가
    남아 있어 반입이 그것으로 찾는다.

    RESTRICT — 쓰는 기종이 있는 형태는 못 지운다."""
    """탁상형·플로어형처럼 생김새. 같은 계열 안에서 갈리므로 계열이 아니라 여기 있다."""

    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )
    """**계열과 따로 둔다.** 계열은 살아 있는데 그중 한 기종만 단종되는 일이 흔하다."""
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """사양으로 못 담는 것 중 이 기종만의 단서."""

    raw_specs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    """제조사 카탈로그의 **사양 원문 그대로.**

    ## 왜 통째로 남기나

    정의로 세운 칸은 사양값(`ModelSpecValue`)이 갖는다. 하지만 원본에는 정의가 없는
    키가 950종 넘게 있고, 그 값 1,400여 건이 지금까지 **버려지고 있었다.** 한 카탈로그에만
    나오는 것이 대부분이라 정의로 세우면 관리 화면이 죽고, 안 세우면 사라진다.

    그래서 **둘 다 한다**: 아는 것은 사양값으로, 전부는 여기에. 반년 뒤 「이 기종
    카탈로그에 뭐라고 적혀 있었나」 를 물을 자리가 생긴다.

    ## JSONB 인 이유 — ADR 0005 와 어긋나지 않는다

    거기서 JSONB 를 물린 것은 **정의를 통제하기 위해서**였다(RESTRICT·쓰임 수).
    이 칸은 정의하는 자리가 아니라 **보존하는 자리**다 — 아무것도 이것을 참조하지
    않고, 검색도 이것을 안 본다. 「모르는 것을 버리지 않되 아는 척도 안 한다.」
    """

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
    __table_args__ = (
        # **부서관리번호는 부서 안에서만 유일하다.** 전사로 걸면 부서마다 다른
        # 체계를 쓰는 번호가 서로 충돌하고, 그때 막히는 것은 등록하는 사람이다.
        UniqueConstraint(
            "owner_workspace_id", "dept_asset_no", name="uq_equipment_dept_asset_no"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    """자산번호. **사람이 현장에서 부르는 이름이자 유일 키다** — 라벨에 붙어 있고,
    다른 시스템과 대조할 때도 이것으로 맞춘다."""
    name: Mapped[str] = mapped_column(String(200))
    """현장 호칭. **카탈로그의 기종명과 다른 칸이다** — 「3동 만능기」 로 불리는 것이
    실재하고, 사람이 찾을 때 치는 말은 그쪽이다."""

    dept_asset_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    """부서관리번호. **유일성은 부서 안에서만 건다**(아래 UniqueConstraint) — 부서마다
    자기 체계라 전사로 걸면 서로 다른 장비가 충돌하고, 그때 등록이 막힌다."""

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
    """제조번호. **유일성을 안 건다** — 제조사가 같은 번호를 다른 계열에 다시 쓰고,
    라벨이 지워져 못 읽는 대도 있다. 못 적는다고 등록을 막을 값이 아니다."""

    category_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """**카탈로그에 연결되지 않은 장비의 장비유형.**

    기종이 있으면 분류는 그 기종의 계열이 갖는다(ADR 0006) — 그때 이 칸은 비운다.
    두 곳에 남겨 두면 계열의 분류를 고친 날 이 장비만 옛 분류를 가리킨 채 남고,
    그 어긋남은 아무 화면에도 안 보인다.

    자작 장비·미등록 장비가 실재하는데 그것도 「무슨 종류의 장비냐」 에는 답해야
    한다 — 답 못 하면 검색과 목록에서 통째로 빠진다."""

    maker_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """카탈로그 미연결일 때만 쓰는 **표시용** 제조사·모델명.

    **검색은 이 둘을 안 본다.** 온톨로지의 제조사 값과 이어져 있지 않아서, 여기 적힌
    「인스트론」 과 축의 「Instron」 은 서로 다른 글자다. 카탈로그에 연결하는 순간
    서버가 이 칸들을 비운다 — 같은 사실이 두 곳에 남으면 어느 쪽이 맞는지 알 수 없다.

    그래도 두는 이유: 이 칸이 없으면 자작 장비의 제조사를 적을 자리가 아예 없고,
    사람은 그것을 비고에 적는다. 비고에 적힌 것은 아무도 못 찾는다."""

    owner_workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    """보유 부서. **비울 수 없다** — 장비에는 반드시 관리하는 부서가 있다.

    전에는 NULL 이 「전사 공용」 을 겸했는데, 그러면 공용으로 표시하는 순간 관리
    부서를 잃었다. 「누가 관리하나」 와 「다른 부서도 쓸 수 있나」 는 다른 물음이라
    칸을 나눈다(`shared_use`).

    RESTRICT 인 이유: 부서를 지우면서 장비가 함께 사라지면, 그 장비로 잰 데이터가
    가리킬 곳을 잃는다. 부서는 지우는 것이 아니라 보관하거나 합친다."""

    shared_use: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    """다른 부서도 쓸 수 있는 장비인가. **가시성이 아니라 사실이다** — 누가 볼 수
    있느냐는 부서의 공개 설정이 정하고(`visible_equipment`), 이 칸은 찾은 사람에게
    「빌릴 수 있나」 를 말해 준다. 그 답이 없으면 검색은 절반만 한 것이다."""

    site_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    """거점(온톨로지 축 site). 공장·연구소처럼 **가려면 이동해야 하는 단위**.

    **비울 수 없다** — 장비는 어딘가에 놓여 있고, 어디 있는지 모르는 장비는 찾아도
    소용이 없다. RESTRICT: 쓰는 장비가 있는 거점은 못 지운다."""
    location: Mapped[str] = mapped_column(String(200))
    """거점 안의 자리. 3동 201호. 자유 문자열로 둔다 — 이것까지 축으로 만들면
    호실 하나 바뀔 때마다 온톨로지를 고쳐야 한다."""

    status: Mapped[str] = mapped_column(
        String(20), default="operational", server_default="operational", index=True
    )
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    """도입일. 우리 것이 된 날이다 — 만들어진 날(`manufactured_year`)과 다르다."""
    manufactured_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """제조연도. **연도까지만 적는다** — 명판에도 카탈로그에도 월일은 대개 없고,
    없는 것을 1월 1일로 지어내면 그 날짜로 수명을 세는 사람이 생긴다."""
    retired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    """폐기일. **상태가 `retired` 일 때만 값이 있다** — 되돌리면 서버가 비운다.
    남겨 두면 가동 중인 장비에 폐기일이 붙어 있고, 목록은 그것을 그대로 그린다."""

    calibration_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    """교정 대상인가. **이력만으로는 못 가른다** — 이력이 없는 장비가 「대상이 아님」
    인지 「빠뜨린 것」 인지 구별되지 않고, 그 둘은 할 일이 정반대다."""
    calibration_interval_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """교정 주기(개월). 대상이면 적는다 — 마지막 교정일에 더해 **차기일을 계산**한다.
    성적서에 적힌 차기일이 있으면 그쪽이 언제나 이긴다(기관이 정한 날이 진실이다)."""

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

    **시험 항목과 별개의 칸이다.** 장비가 20 kN 을 낼 수 있다는 것과 그 값이 지금 믿을
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
    provider_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    """교정 기관(온톨로지 축 `calibration_provider`).

    **자유 문자열로 두면 갈린다.** 같은 기관이 「한국계량측정협회」 와 「(주)한국계량
    측정협회」 로 적히면 그 둘은 서로 다른 기관이 되고, 「이 기관이 교정한 장비」 를
    묻는 순간 절반만 답한다."""
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

    requires_accessory: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    """**본체가 아니라 옵션 부속(챔버·노·클램프)이 있어야 나오는 값.** 카탈로그가
    「-180~320 °C」 를 항온조 옵션 기준으로 적는 일이 흔한데, 그것을 본체 값처럼 두면
    검색이 갖고 있지도 않은 챔버를 전제로 「80 °C 됨」 이라고 답한다 — ADR 0003 이
    막으려던 바로 그 오답. 표시는 남기고 판정을 가른다."""
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


class ModelFreeSpec(Base):
    """**이 기종만의 사양** — 정의 없이 기종에 직접 붙는 이름·값·단위.

    ## 왜 정의 없이 두나

    카탈로그 원본의 사양 키는 950종이 넘고 그중 803종이 **한 기종에만** 나온다(2026-09-12
    실측). 전부 정의로 세우면 「사양 추가」 목록이 1,100줄이 되어 원하는 칸을 못 찾고,
    못 찾은 사람은 새 칸을 또 만든다 — 같은 값이 둘로 갈리는 그 실패가 ADR 0005 를 쓰게 한
    원인이다. 그렇다고 버리면 「이 점도계의 스핀들 종류」 처럼 그 기종을 아는 데 꼭 필요한
    것이 원문 JSON 안에만 남는다.

    그래서 세 자리로 가른다:

        정의 있는 사양   여러 기종이 공유하는 수치 — 비교·대표 사양·검색이 된다
        이 기종만의 사양 한 기종에만 있는 수치·서술 — 값은 들어가고 정의 목록은 안 부푼다
        원문             옮겨 적기 전의 전부 — 근거

    ## 값은 글자다

    비교 대상이 아니라서 수치 칸을 나누지 않는다. 같은 이름이 여러 기종에 쌓여 비교할 일이
    생기면 그때 **정의로 세운다**(`promote`) — 이름·단위·분류를 사람이 확인하고 누르는
    순간 정식 정의가 되고, 그 값들은 `model_spec_values` 로 옮겨 간다.

    ## 반입은 채우기만 한다

    `source_key` 가 있는 줄은 반입이 만든 것이다. 다시 반입해도 있는 줄은 **안 덮는다** —
    사람이 이름을 고쳐 둔 것이 돌아오면 안 된다.
    """

    __tablename__ = "model_free_specs"
    __table_args__ = (
        # NULL 은 서로 다르다(Postgres) — 손으로 더한 줄(source_key 없음)은 몇이든 된다.
        UniqueConstraint("model_id", "source_key", name="uq_model_free_specs_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment_models.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(150))
    """사람이 읽는 이름. 반입이 온톨로지 라벨을 알면 그것, 모르면 원본 키 그대로 — 지어내지
    않는다. 사람이 화면에서 고친다."""
    value_text: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    """원본 카탈로그의 키(`stroke_mm_pk_pk`). 재반입의 멱등 열쇠이고, 「정의로 세우기」 가
    같은 키를 가진 다른 기종의 줄을 함께 옮길 때 쓴다."""
    origin: Mapped[str] = mapped_column(
        String(10), default="manual", server_default="manual", nullable=False
    )
    """`catalog`(반입) · `manual`(사람)."""
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


class EquipmentSpecValue(Base):
    """이 **개체**가 실제로 갖는 사양값 하나 — 카탈로그 위에 덮는 실측.

    ## 복사가 아니라 겹쳐 보기다

    등록할 때 기종 사양을 통째로 복사해 두지 않는다. 개체는 **카탈로그와 다른 값만**
    갖고, 나머지는 기종 사양이 그대로 보인다. 전부 복사하면 두 가지를 잃는다 —
    카탈로그가 개정돼도 안 따라오고, 무엇보다 **어느 값이 실측인지 구별이 사라진다.**

    시험 항목을 복사로 둔 것(ADR 0004)과 다른 판단인 이유: 시험 항목은 「그때 그렇게 판단했다」
    는 스냅샷이라 굳는 것이 맞고, 사양 수치는 「카탈로그가 말하는 것」 과 「우리가 잰
    것」 이 **둘 다 남아야** 한다. 화면은 둘을 함께 보여 준다.

    ## 검색축에 이어진 사양은 시험 조건이 된다

    기종 사양이 그랬듯이(`conditions_from_specs`), 여기 적은 실측도 이 장비의 시험 항목
    조건을 갱신한다. 다만 **손으로 고쳐 둔 조건은 안 덮는다** — 사람이 재서 적은
    값을 사양표가 덮으면 그 손실은 검색 결과가 어긋난 날에야 드러난다.
    """

    __tablename__ = "equipment_spec_values"
    __table_args__ = (
        UniqueConstraint("equipment_id", "definition_id", name="uq_equipment_spec_values_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE"), index=True
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    """RESTRICT — 쓰는 값이 있는 정의는 못 지운다. 기종 사양과 같은 규칙이다."""

    num_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    bool_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    measured_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    """언제 잰 값인가. **3년 전 실측은 사양서보다 나을 것이 없다** — 지그도 챔버도
    그동안 바뀐다. 화면이 날짜를 함께 보여 줘야 사람이 그것을 판단할 수 있다."""

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("spec_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """성적서·시험 보고서 같은 근거 문서. 기종 사양의 출처와 같은 표를 쓴다."""
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
