"""시험법 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condition_key_id: uuid.UUID
    condition_key: str
    condition_label: str
    si_unit: str
    display_unit: str
    """**값과 단위를 함께 준다.** 숫자만 주면 화면이 조건 정의를 또 조회해야 하고,
    그 조회를 빠뜨린 화면은 20 이 N 인지 kN 인지 모른 채 그린다."""
    min_value: float | None
    max_value: float | None
    text_value: str | None
    is_mandatory: bool
    note: str | None


class MethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    edition: str | None
    title: str
    test_item: str | None
    test_item_term_id: uuid.UUID | None
    body: str | None
    status: str
    superseded_by_code: str | None
    """무엇으로 대체됐나. **끊어 두면 옛 판을 보던 사람이 다음 판을 못 찾는다.**"""
    summary: str | None
    workspace_slug: str | None
    equipment_count: int
    """이 시험법을 할 수 있다고 등록된 장비 수. 0 이면 그 규격은 **지금 우리가
    못 하는 시험**이다 — 그 사실이 목록에 보여야 한다."""
    requirements: list[RequirementOut]
    created_at: datetime
    can_edit: bool


class MethodCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    edition: str | None = Field(default=None, max_length=30)
    title: str = Field(min_length=1, max_length=300)
    test_item_term_id: uuid.UUID | None = None
    body_term_id: uuid.UUID | None = None
    summary: str | None = None
    workspace_slug: str | None = None
    """비우면 전사 공용 — 공개 규격은 대개 이쪽이다."""


class MethodUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    edition: str | None = None
    test_item_term_id: uuid.UUID | None = None
    body_term_id: uuid.UUID | None = None
    summary: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|superseded)$")
    superseded_by_id: uuid.UUID | None = None


class RequirementUpsertRequest(BaseModel):
    """요구 조건 하나를 넣거나 고친다. 같은 조건이 이미 있으면 덮어쓴다.

    **한쪽을 비울 수 있다.** 20 kN 이상은 min 만 있고 max 가 없다 — 0 으로 채우면
    상한이 0 인 것과 구별되지 않는다.
    """

    condition_key_id: uuid.UUID
    min_value: float | None = None
    max_value: float | None = None
    text_value: str | None = Field(default=None, max_length=200)
    is_mandatory: bool = True
    note: str | None = None
