"""물성 ↔ 시험 항목 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestItemPropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_item_term_id: uuid.UUID
    test_item: str
    property_term_id: uuid.UUID
    property: str
    property_code: str | None
    """`mechanical.yield_strength` — MaterialTwin 키. 이름이 바뀌어도 이것이 남는다."""
    status: str
    source: str
    note: str | None
    confirmed_at: datetime | None
    created_at: datetime


class PropertyOut(BaseModel):
    """물성 하나와 그것을 내는 시험 항목들. 목록 화면이 그리는 줄."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    value: str
    code: str | None
    domain: str | None
    """`mechanical` · `thermal` … MaterialTwin 키의 앞 토막. 화면이 이것으로 묶는다."""
    symbol: str | None
    si_unit: str | None
    aliases: list[str]
    links: list[TestItemPropertyOut]


class TestItemPropertyCreateRequest(BaseModel):
    test_item_term_id: uuid.UUID
    property_term_id: uuid.UUID
    note: str | None = Field(default=None, max_length=2000)
    """덧붙는 조건 — 「신율계 필요」 처럼."""


class TestItemPropertyUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(suggested|confirmed)$")
    note: str | None = Field(default=None, max_length=2000)
