"""항목 정의·값 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class AttributeDefinitionOut(BaseModel):
    id: uuid.UUID
    target: str
    key: str
    label: str
    kind: str
    unit: str
    choices: list[str]
    condition_key_id: uuid.UUID | None
    condition_key_label: str | None
    vocabulary_id: uuid.UUID | None
    vocabulary_slug: str | None
    status: str
    is_required: bool
    help: str | None
    sort_order: int
    is_active: bool
    merged_into_id: uuid.UUID | None
    value_count: int
    """이 항목으로 적힌 값의 수. 초안 목록을 건수순으로 보면 무엇을 정식으로 올릴지 보인다."""
    created_at: datetime


class AttributeDefinitionCreateRequest(BaseModel):
    """시스템 관리자가 정식(또는 미리 준비하는 초안) 항목을 만든다."""

    target: str
    label: str = Field(min_length=1, max_length=150)
    key: str | None = Field(default=None, max_length=60)
    kind: str = "text"
    unit: str = Field(default="", max_length=20)
    choices: list[str] = Field(default_factory=list)
    condition_key_id: uuid.UUID | None = None
    vocabulary_id: uuid.UUID | None = None
    status: str = "standard"
    is_required: bool = False
    help: str | None = Field(default=None, max_length=2000)
    sort_order: int = 0


class AttributeDefinitionUpdateRequest(BaseModel):
    """안 보낸 칸은 그대로. `kind` 는 값이 하나도 없을 때만 바뀐다."""

    label: str | None = Field(default=None, min_length=1, max_length=150)
    key: str | None = Field(default=None, min_length=1, max_length=60)
    kind: str | None = None
    unit: str | None = Field(default=None, max_length=20)
    choices: list[str] | None = None
    condition_key_id: uuid.UUID | None = None
    vocabulary_id: uuid.UUID | None = None
    status: str | None = None
    is_required: bool | None = None
    help: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = None
    is_active: bool | None = None


class AttributeMergeRequest(BaseModel):
    target_id: uuid.UUID
    """남는 쪽. 값이 이쪽으로 옮겨 가고 원래 항목은 꺼진다."""


class AttributeValueIn(BaseModel):
    """값 하나. `definition_id` 가 있으면 그 항목, 없으면 `new_label` 로 **초안을 새로
    만든다.**

    종류별로 채우는 칸이 다르다 — number: num_value(+unit) · range/condition: num_min·
    num_max(+unit) · text/choice: text_value · boolean: bool_value · date: date_value ·
    term: term_id · method: method_id. 다른 칸은 무시한다.
    """

    definition_id: uuid.UUID | None = None
    new_label: str | None = Field(default=None, min_length=1, max_length=150)
    new_kind: str = "text"
    """새 초안의 종류. definition_id 가 있으면 안 본다."""
    num_value: float | None = None
    num_min: float | None = None
    num_max: float | None = None
    unit: str = Field(default="", max_length=20)
    text_value: str | None = Field(default=None, max_length=4000)
    bool_value: bool | None = None
    date_value: date | None = None
    term_id: uuid.UUID | None = None
    method_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class AttributeValueOut(BaseModel):
    definition_id: uuid.UUID
    label: str
    kind: str
    status: str
    """`draft` 면 초안 — 화면은 표시로 가르고, MCP 는 비교·집계에 쓰지 말라고 적는다."""
    unit: str
    num_value: float | None
    num_min: float | None
    num_max: float | None
    text_value: str | None
    bool_value: bool | None
    date_value: date | None
    term_id: uuid.UUID | None
    term_value: str | None
    method_id: uuid.UUID | None
    method_code: str | None
    note: str | None
    display: str
    """사람이 읽는 한 줄. 「-40 ~ 125 ℃」 「ISO 6892-1」 「있음」. 화면과 MCP 가 같은 글자를
    쓴다."""
