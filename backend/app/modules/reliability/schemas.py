"""신뢰성 시험 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.attributes.schemas import AttributeValueIn, AttributeValueOut
from app.modules.search.schemas import SearchHit


class ReliabilityTestItemOut(BaseModel):
    """이 시험이 쓰는 시험 항목 하나와, 그 항목을 할 수 있는 **이 부서의** 장비 수."""

    term_id: uuid.UUID
    value: str
    equipment_count: int
    """이 부서 장비 중 이 시험 항목이 되는 것. 내가 볼 수 있는 것만 센다 — 검색과 같은 규칙.
    0 이면 시험은 정해졌는데 돌릴 장비가 이 부서에 없다는 뜻이다."""


class ReliabilityTestOut(BaseModel):
    id: uuid.UUID
    workspace_slug: str
    workspace_name: str
    name: str
    purpose: str
    test_items: list[ReliabilityTestItemOut]
    attributes: list[AttributeValueOut]
    """항목 값 — 정식이 먼저, 초안이 뒤. `status` 로 가른다."""
    attachment_count: int = 0
    """붙은 그림 수. **목록이 낱장을 받지 않는다** — 줄마다 그림을 받아 오면 스무 줄에
    쉰 번을 왕복한다. 수만 보이고, 누르면 그때 받는다."""
    can_edit: bool
    """요청한 사람이 고칠 수 있나 — 그 부서의 관리자 또는 시스템 관리자. 화면이 단추를
    보일지 정하는 데 쓴다. 판정은 서버가 한다."""
    created_at: datetime
    updated_at: datetime


class ReliabilityTestCreateRequest(BaseModel):
    workspace_slug: str
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(default="", max_length=4000)
    test_item_term_ids: list[uuid.UUID] = Field(default_factory=list)
    attributes: list[AttributeValueIn] = Field(default_factory=list)
    """항목 값. `definition_id` 가 없고 `new_label` 이 있으면 초안 항목이 생긴다."""


class ReliabilityTestUpdateRequest(BaseModel):
    """안 보낸 칸은 그대로. `test_item_term_ids` 는 보내면 **통째로** 바뀐다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = Field(default=None, max_length=4000)
    test_item_term_ids: list[uuid.UUID] | None = None
    attributes: list[AttributeValueIn] | None = None
    """보내면 통째로 바뀐다 — 시험 항목과 같은 규칙."""


class SkippedConditionOut(BaseModel):
    """물음에서 뺀 조건과 그 이유. **조용히 빼지 않는다** — 다 본 것처럼 읽힌다."""

    label: str
    reason: str


class CapabilityItemOut(BaseModel):
    """이 시험이 쓰는 시험 항목 하나에 대한 답."""

    term_id: uuid.UUID
    value: str
    total: int
    """조건을 걸고도 남은 장비 수. `hits` 는 그중 앞에서부터 상한까지다."""
    unmet_count: int
    """조건이 **안 되는** 것으로 판정돼 빠진 장비 수. 0 대라는 답이 「등록이 없어서」 인지
    「조건이 안 맞아서」 인지를 가른다."""
    hits: list[SearchHit]


class CapabilityOut(BaseModel):
    """「이 시험, 어느 장비로 돌리나」 의 답 — 조건 속성을 그대로 검색 조건으로 옮긴 것."""

    test_id: uuid.UUID
    conditions_asked: int
    """검색에 넘긴 조건 물음 수. 범위 하나는 물음 둘이다(위로 얼마까지 · 아래로 얼마까지)."""
    skipped: list[SkippedConditionOut]
    items: list[CapabilityItemOut]
