"""신뢰성 시험 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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


class ReliabilityTestUpdateRequest(BaseModel):
    """안 보낸 칸은 그대로. `test_item_term_ids` 는 보내면 **통째로** 바뀐다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = Field(default=None, max_length=4000)
    test_item_term_ids: list[uuid.UUID] | None = None
