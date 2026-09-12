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


class LinkBulkRequest(BaseModel):
    """제안 여럿을 **한 번에** 확인하거나 되돌린다.

    254건을 한 줄씩 누르게 두면 아무도 끝내지 못하고, 그 사이 연결은 계속 「기계가 그렇게
    말했다」 로 남는다. 사람이 보는 단위는 줄(한 시험 항목이 내는 물성들)이라 그 단위로
    받는다.
    """

    link_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    """한 번에 500까지. 넘으면 거르고 나눠서 한다 — 한 번에 다 누르는 것은 확인이 아니다."""
    status: str = Field(pattern="^(suggested|confirmed)$")
    """`confirmed` 가 확인, `suggested` 가 되돌리기(잘못 눌렀을 때)."""


class LinkBulkResult(BaseModel):
    changed: int
    """실제로 바뀐 줄 수. 이미 그 상태였던 것은 안 센다 — 「254건 확인」 이라 말해 놓고
    그중 200이 이미 확인이었으면 사람이 자기가 무엇을 했는지 모른다."""
    links: list[TestItemPropertyOut]
    """바뀐 줄들. 화면이 다시 안 받아도 되게."""


class TestItemPropertyUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(suggested|confirmed)$")
    note: str | None = Field(default=None, max_length=2000)
