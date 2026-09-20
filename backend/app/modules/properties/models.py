"""물성 ↔ 시험 항목 — **어떤 시험으로 어떤 물성을 얻나.**

검색 사슬의 **앞에 한 칸을 더 붙인다.**

    물성  ⇄  시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
     N:M

사람이 실제로 묻는 말은 「인장 되는 장비」 보다 「**인장강도** 알고 싶은데 어디서 하나」
「**Tg** 재는 장비 있나」 에 가깝다. 시험 항목에서 시작하는 사슬은 그 물음을 받지 못한다
— 물성이 무슨 시험으로 나오는지를 묻는 사람이 이미 알아야 한다.

## 왜 N:M 인가

    인장 하나        ->  인장강도 · 항복강도 · 영률 · 연신율 · 포아송비
    유리전이온도 하나 <-  DSC · DMA · TMA   (셋 다 후보고, 장비가 서로 다르다)

한 칸으로 두면 어느 쪽이든 하나를 버린다.

## 물성의 정본은 MaterialTwin 키다

물성 항목은 기준정보 축 `property` 의 값이고, 그 값의 `code` 가 `mechanical.yield_strength`
같은 MaterialTwin 키다. 재료 물성 쪽(MatNexus)이 같은 271 키를 쓰므로 세 시스템이 **같은
말**을 한다. 한글 이름을 우리가 따로 지어 대응표를 두는 길은 MatNexus 가 먼저 가 봤고,
실측으로 9개를 잇는 데서 멈췄다.

## 기계가 제안하고 사람이 확인한다

첫 채움은 카탈로그 온톨로지(`test_items.json` 의 measurands)와 MaterialTwin 능력행에서
자동으로 만든다. 그것은 **제안**(`suggested`)이고, 화면에서 사람이 보고 `confirmed` 로
올린다. 구별을 두는 이유: 자동 판정이 「유리전이온도 ← 딜라토메트리」 처럼 그럴듯한
오답을 만들 수 있고, 그것이 확인된 것과 같은 얼굴로 앉아 있으면 아무도 되짚지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 연결의 상태.
#:   suggested  기계가 만들었다 — 온톨로지·MaterialTwin 에서. 사람이 아직 안 봤다
#:   confirmed  사람이 보고 맞다고 했다
LINK_STATUSES = ("suggested", "confirmed")

#: 어디서 왔나. 보고서와 화면이 「왜 이 연결이 있나」 에 답하는 근거다.
#:   ontology      `source/catalog/ontology/test_items.json` 의 measurands
#:   materialtwin  MaterialTwin 능력행 (기종, 물성, 기법)
#:   manual        사람이 화면에서 더했다
#:   agent         AI 가 규격·문헌을 읽고 제안했다 — 늘 `suggested` 로 들어오고 사람이 확인한다
LINK_SOURCES = ("ontology", "materialtwin", "manual", "agent")


class TestItemProperty(Base):
    """시험 항목 하나가 물성 하나를 낸다 — 그 한 줄.

    `note` 에는 **덧붙는 조건**이 온다. MaterialTwin 능력행의 기법이 그것을 적고 있다:
    「단축 인장 — **신율계** 변형률」. 영률은 인장기만으로는 안 나오고 신율계가 붙어야
    한다는 사실이 여기 남는다.
    """

    __tablename__ = "test_item_properties"
    __table_args__ = (
        UniqueConstraint(
            "test_item_term_id", "property_term_id", name="uq_test_item_properties_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_item_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        index=True,
    )
    """기준정보 축 `test_item` 의 값. RESTRICT — 연결이 있는 시험 항목은 못 지운다."""
    property_term_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
        index=True,
    )
    """기준정보 축 `property` 의 값. `code` 가 MaterialTwin 키다."""

    status: Mapped[str] = mapped_column(
        String(20), default="suggested", server_default="suggested", index=True
    )
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
