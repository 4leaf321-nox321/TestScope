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
    requires_accessory: bool
    """옵션 부속(챔버·노)이 있어야 나오는 범위. 검색이 「됨」 대신 「부속 있으면」 으로
    답한다."""
    note: str | None


class TestItemCatalogRow(BaseModel):
    """시험 항목 한 줄 — **사슬 전체의 수.** 0 이 곧 공백이다.

    물성  ⇄  시험 항목  →  규격  →  계열/기종  →  보유 장비
    """

    id: uuid.UUID
    value: str
    code: str | None
    aliases: list[str]
    properties_total: int
    properties_confirmed: int
    methods_total: int
    """이 시험 항목의 규격으로 정해진 것."""
    methods_with_requirements: int
    series_count: int
    model_count: int
    equipment_count: int
    """**내가 볼 수 있는** 보유 장비. 남의 부서가 가린 것은 안 센다."""
    condition_keys: list[str]
    """검색축 라벨. 비어 있으면 검색이 축 일곱 개를 다 묻는다."""


class TestItemSeriesOut(BaseModel):
    id: uuid.UUID
    name: str
    maker: str | None
    category: str | None
    model_count: int
    method_codes: list[str]


class TestItemEquipmentOut(BaseModel):
    id: uuid.UUID
    asset_no: str
    name: str
    workspace: str | None
    status: str


class TestItemMethodOut(BaseModel):
    id: uuid.UUID
    code: str
    edition: str | None
    title: str
    has_requirements: bool
    series_count: int


class TestItemPropertyLinkOut(BaseModel):
    link_id: uuid.UUID
    property_term_id: uuid.UUID
    property: str
    property_code: str | None
    status: str


class TestItemConditionKeyOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    unit: str


class TestItemCatalogOut(BaseModel):
    """시험 항목 상세 — 물성·규격·계열·보유 장비·검색축을 한 자리에."""

    id: uuid.UUID
    value: str
    code: str | None
    aliases: list[str]
    properties: list[TestItemPropertyLinkOut]
    methods: list[TestItemMethodOut]
    series: list[TestItemSeriesOut]
    equipment: list[TestItemEquipmentOut]
    condition_keys: list[TestItemConditionKeyOut]
    can_edit: bool


class TestItemConditionKeysRequest(BaseModel):
    condition_key_ids: list[uuid.UUID] = Field(max_length=20)


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
    requires_accessory: bool = False
