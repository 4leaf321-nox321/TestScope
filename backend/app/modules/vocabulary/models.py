"""기준정보 — **축과 값과 표기.**

사람이 타이핑하는 짧은 문자열(제조사·장비 분류·시험 항목·거점 …)을 표로 올리고,
쓰는 쪽은 외래키로 가리킨다. 그래야 두 표기를 묶는 것이 UPDATE 한 문장이 되고,
값 이름을 바꾸는 것이 한 행이 된다.

    vocabularies         축    manufacturer · test_item · equipment_category …
    vocabulary_terms     값    인장 · 압축 · 만능재료시험기
    vocabulary_aliases   표기  UTM -> 만능재료시험기

## 왜 세 표인가

**축과 값을 나누는 이유**: 축마다 성질이 다르다. 입력 정책(open/closed)도, 부모
축이 무엇인지도 축에 붙는다. 값마다 그것을 물으면 같은 답을 수만 번 저장하는 셈이다.

**별칭을 나누는 이유**: 별칭은 **예방**이다. UTM 을 만능재료시험기의 별칭으로
등록해 두면 값을 만들 때 그것까지 뒤져서 애초에 중복이 안 생긴다 — 사후에 합치는
것보다 싸다.

## 기준정보는 전사 공용이다

제조사가 부서마다 다를 이유가 없다. 이 시스템이 답하려는 물음("어느 부서든 그
시험을 할 수 있는 장비가 있나")이 부서를 가로지르므로, 축이 부서마다 갈리면 그
물음 자체가 성립하지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

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

#: 입력 정책. 값이 아니라 **축**에 붙는다.
#:
#:   open   — 누구나 피커에서 새 값을 추가할 수 있다. 제조사·모델처럼 계속
#:            늘어나는 축. 승인 대기를 두지 않는다 — 기다리게 하면 피커가 멈추고,
#:            그러면 사람은 시스템 밖에서 일한다. 드리프트는 사후 병합으로 푼다.
#:   closed — 관리자가 등록한 값만 고른다. 시험 항목처럼 **검색의 축이 되는 것**에
#:            쓴다. 여기서 오타가 값이 되면 그 장비는 영영 검색에 안 걸린다.
ENTRY_POLICIES = ("open", "closed")

#: 값의 상태.
#:   active     — 피커에 뜬다.
#:   deprecated — 피커에서 숨기되 **이미 가리키고 있는 것은 그대로 둔다.**
#:                지우면 그 장비가 무엇이었는지 알 수 없게 된다.
TERM_STATUSES = ("active", "deprecated")


#: 축이 어느 층의 것인가.
#:
#:   equipment  보유 장비 — 우리가 가진 그 한 대에 붙는다
#:   catalog    카탈로그 — 제조사가 파는 계열·기종에 붙는다
#:   method     시험법 — 규격에 붙는다
#:   common     여러 층이 함께 쓴다. **얼버무리는 자리가 아니다**
VOCABULARY_DOMAINS = ("equipment", "catalog", "method", "common")

#: 화면이 쓰는 이름. 코드가 slug 를 걸고 사람은 이 말을 읽는다.
VOCABULARY_DOMAIN_LABELS = {
    "equipment": "보유 장비",
    "catalog": "카탈로그",
    "method": "시험법",
    "common": "공통",
}


class Vocabulary(Base):
    """축 하나.

    마이그레이션으로 심고 API 로는 안 만든다 — 축이 늘어나는 것은 스키마가 바뀌는
    일이지 데이터가 늘어나는 일이 아니다. 코드가 slug 로 축을 거는 자리가 있다.
    """

    __tablename__ = "vocabularies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    """코드가 거는 이름. manufacturer 처럼 안 바뀌는 것."""
    domain: Mapped[str] = mapped_column(
        String(20), default="common", server_default="common", index=True
    )
    """**어디의 축인가.** 기준정보 화면이 이것으로 묶어 보여 준다.

    축이 일곱을 넘어가면 한 목록으로는 「이게 어디 쓰이는 값이지」 를 알 수 없다 —
    제조사와 규격 제정기관이 나란히 서 있으면, 장비를 등록하러 온 사람이 제정기관에
    회사 이름을 넣는다. 실제로 그렇게 갈린다.

    `common` 은 얼버무리는 자리가 아니라 **정말 여러 층이 쓰는 축**이다. 시험 항목이
    그렇다 — 장비의 시험 항목·계열의 시험 항목·시험법이 전부 그것을 가리킨다."""
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    """이 축이 무엇인지 한 줄. 화면이 그대로 보여 준다 — 고르는 사람이 축의 뜻을
    모르면 비슷한 축 둘 중 아무 데나 값을 넣는다."""

    entry_policy: Mapped[str] = mapped_column(
        String(10), default="open", server_default="open"
    )
    attribute_schema: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    """**이 축의 값이 갖는 칸.** `[{"key": "symbol", "label": "기호", "kind": "text"}, …]`.

    값의 `attributes` 는 자유 JSON 이라 화면이 무엇을 그릴지 모른다 — 물성은 기호·단위·
    설명을, 시험 항목은 대표 조건을 갖는데, 축이 그것을 말하지 않으면 편집 화면은 JSON 을
    통째로 보이는 수밖에 없고 그러면 아무도 안 고친다. **축에 한 번 적는다** — 값마다
    물으면 같은 답을 수백 번 저장하는 셈이다(`parent_slug` 와 같은 판단).

    `kind` 는 `text` · `number` · `list`(쉼표로 나눈 문자열 목록). 스키마에 없는 키가 값에
    있어도 지우지 않는다 — 반입이 넣은 것이고, 화면은 그것을 「그 밖의 속성」 으로 보인다."""
    parent_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    """이 축의 값이 어느 축 아래 사는가. test_method 의 부모는 test_item 이다.

    **계약을 축 수준에 한 번만 적는다.** 값마다 "이건 어느 축의 부모냐" 를 물으면
    같은 답을 수만 번 저장하는 셈이고, 잘못된 축을 가리키는 값이 생긴다."""

    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VocabularyTerm(Base):
    """값 하나."""

    __tablename__ = "vocabulary_terms"
    __table_args__ = (
        # **유일성은 비교키로 건다.** value 로 걸면 인장 과 인장(뒤 공백) 이 둘 다
        # 들어간다 — 눈에 같아 보이는데 DB 는 다르게 본다.
        UniqueConstraint("vocabulary_id", "normalized", name="uq_vocabulary_terms_norm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vocabulary_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("vocabularies.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str] = mapped_column(String(200))
    """보여 주는 값. 사람이 적은 표기를 정리만 해서 그대로 담는다(shared.text.clean)."""
    normalized: Mapped[str] = mapped_column(String(200), index=True)
    """비교키(shared.text.compare_key). 유일성과 조회가 이걸로 돈다."""
    code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    """코드가 이 값을 이름이 아니라 **키로** 걸어야 할 때. 검색 화면이 시험 항목을
    tensile 로 거는 자리다 — 이름이 바뀌어도 검색이 안 깨진다."""

    parent_term_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    """상위 축의 값.

    **비워 둘 수 있다.** 부모를 모르는 값이 있어도 시스템이 멈추면 안 된다 —
    부모가 없으면 좁히기가 안 될 뿐이다. 부모가 지워지면 NULL 이 된다: 값 자체는
    살아 있어야, 가리키던 장비가 무엇이었는지가 그대로 남는다."""

    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    """이 값이 갖는 부속 정보. 시험 항목이면 대표 조건 키 목록 같은 것."""

    status: Mapped[str] = mapped_column(String(20), default="active", index=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VocabularyAlias(Base):
    """다른 표기. UTM -> 만능재료시험기.

    **예방이 목적이다.** 값을 만들 때 별칭까지 뒤져서 애초에 중복이 안 생기게 한다.
    """

    __tablename__ = "vocabulary_aliases"
    __table_args__ = (
        UniqueConstraint("vocabulary_id", "normalized", name="uq_vocabulary_aliases_norm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vocabulary_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("vocabularies.id", ondelete="CASCADE"), index=True
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("vocabulary_terms.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str] = mapped_column(String(200))
    normalized: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


#: 조건이 담는 것.
#:   range   — 범위. 온도·하중·주파수처럼 **숫자 구간**으로 답하는 것. 검색이
#:             "80도가 그 구간 안에 드나" 를 묻는다.
#:   choice  — 정해진 목록에서 고르는 것. 시험 모드(인장/압축), 챔버 종류.
#:   boolean — 있나 없나. 항온조 유무, 신율계 유무.
CONDITION_KINDS = ("range", "choice", "boolean")


class ConditionKey(Base):
    """시험 조건의 **정의**. 온도·하중·변위속도·주파수 …

    ## 왜 표인가

    이 시스템의 검색은 "80도에서 20kN 이상 인장" 처럼 **조건으로** 묻는다. 조건
    이름을 장비마다 자유 문자열로 적게 두면 어떤 장비는 온도, 어떤 장비는 시험온도,
    또 어떤 장비는 Temp 로 적히고 — 그러면 그 셋은 서로 다른 조건이 되어 검색이
    조용히 절반만 답한다.

    ## 단위는 저장과 표시를 나눈다

    값은 **언제나 SI 로 담는다**(si_unit). 사람이 kN 으로 적어도 저장은 N 이다.
    화면이 실무 단위(display_unit)로 바꿔 보여 준다 — 섞어 담으면 20 이 20 N 인지
    20 kN 인지 알 수 없고, 그 둘은 자릿수가 셋 다르다.

    ## 축이 아니라 표인 이유

    기준정보 축(Vocabulary)은 "값의 목록" 이고, 이것은 "칸의 정의" 다. 조건에는
    차원·단위·기본 범위처럼 값이 아닌 계약이 붙는다. 같은 표에 넣으면 축의 값마다
    안 쓰는 칸이 생긴다.
    """

    __tablename__ = "condition_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    """코드와 검색이 거는 이름. temperature · force · crosshead_speed."""
    label: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(10), default="range", server_default="range")

    dimension: Mapped[str] = mapped_column(String(30), default="", server_default="")
    """무엇의 크기인가 — temperature · force · length · time · frequency.
    같은 차원끼리만 환산이 성립한다. 검색이 단위를 바꿔 받을 때 이것을 본다."""
    si_unit: Mapped[str] = mapped_column(String(20), default="", server_default="")
    """**저장 단위.** K · N · m · s · Hz."""
    display_unit: Mapped[str] = mapped_column(String(20), default="", server_default="")
    """화면이 쓰는 실무 단위. degC · kN · mm."""

    choices: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    """kind 가 choice 일 때 고를 수 있는 값. 비어 있으면 아무 문자나 받는 것과 같다."""

    help: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    """끄면 새 입력에서 안 뜬다. **지우지는 않는다** — 이미 그 조건으로 적힌
    장비 시험 항목이 무엇이었는지 알 수 없게 된다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
