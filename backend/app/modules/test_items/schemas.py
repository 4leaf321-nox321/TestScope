"""시험 항목 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LimitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condition_key_id: uuid.UUID
    condition_key: str
    condition_label: str
    si_unit: str
    display_unit: str
    min_value: float | None
    max_value: float | None
    text_value: str | None
    note: str | None


class EquipmentTestItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_id: uuid.UUID
    equipment_asset_no: str
    equipment_name: str
    test_item_term_id: uuid.UUID
    test_item: str
    method_id: uuid.UUID | None
    method_code: str | None
    confidence: str
    verified_on: date | None
    note: str | None
    limits: list[LimitOut]
    created_at: datetime
    can_edit: bool


class EquipmentTestItemCreateRequest(BaseModel):
    equipment_id: uuid.UUID
    test_item_term_id: uuid.UUID
    method_id: uuid.UUID | None = None
    """비워 둘 수 있다 — 규격을 특정하지 않고 "인장은 된다" 만 아는 단계가 있다."""
    confidence: str = Field(default="catalog", pattern="^(catalog|verified|limited)$")
    verified_on: date | None = None
    note: str | None = None


class EquipmentTestItemUpdateRequest(BaseModel):
    method_id: uuid.UUID | None = None
    confidence: str | None = Field(default=None, pattern="^(catalog|verified|limited)$")
    verified_on: date | None = None
    note: str | None = None


class LimitUpsertRequest(BaseModel):
    """조건 한 칸의 범위를 넣거나 덮어쓴다.

    **값은 화면 단위로 받고 서버가 SI 로 바꾸지 않는다** — 프론트가 조건 정의의
    si_unit 을 보고 이미 환산해 보낸다. 환산을 두 곳에서 하면 언젠가 한쪽만
    고쳐지고, 그때 저장된 숫자가 조용히 세 자릿수 틀린다.
    """

    condition_key_id: uuid.UUID
    min_value: float | None = None
    max_value: float | None = None
    text_value: str | None = Field(default=None, max_length=200)
    note: str | None = None
