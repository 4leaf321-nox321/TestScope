"""기준정보 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VocabularyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    label: str
    description: str | None
    entry_policy: str
    parent_slug: str | None
    sort_order: int
    term_count: int
    """값이 몇 개인가. **축 목록에서 이걸 못 보면** 비어 있는 축과 채워진 축이
    같아 보이고, 어디를 채워야 하는지 알 수 없다."""


class TermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vocabulary_slug: str
    value: str
    code: str | None
    parent_term_id: uuid.UUID | None
    parent_value: str | None
    """상위 값의 이름. id 만 주면 화면이 그걸 또 조회해야 한다."""
    status: str
    usage_count: int
    aliases: list[str]
    attributes: dict[str, Any]
    created_at: datetime


class TermCreateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    parent_term_id: uuid.UUID | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TermUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.**

    None 은 "안 바꿈" 이다. 구별하지 않으면 이름 하나 고칠 때마다 코드와 상위 값이
    조용히 지워진다 — 그 손실은 저장 버튼을 누른 사람 눈에 안 보인다.
    """

    value: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    parent_term_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|deprecated)$")
    attributes: dict[str, Any] | None = None


class TermMergeRequest(BaseModel):
    """이 값을 다른 값으로 합친다. 원본은 별칭이 되어 남는다.

    **지우지 않고 별칭으로 남기는 이유**: 같은 오타가 또 들어오는 것을 막는다.
    사후에 합치는 것보다 애초에 안 생기게 하는 것이 싸다.
    """

    target_term_id: uuid.UUID


class AliasCreateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=200)


class ConditionKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    label: str
    kind: str
    dimension: str
    si_unit: str
    display_unit: str
    choices: list[str]
    help: str | None
    sort_order: int
    is_active: bool
    usage_count: int
    """이 조건을 쓰는 역량·요구 수. **끄거나 고치기 전에 보여 준다** — 단위를
    고치면 이미 저장된 그 숫자들의 뜻이 통째로 바뀐다."""


class ConditionKeyCreateRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    """코드와 검색이 거는 이름. 소문자와 밑줄만 — 화면 이름은 label 이 갖는다."""
    label: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="range", pattern="^(range|choice|boolean)$")
    dimension: str = Field(default="", max_length=30)
    si_unit: str = Field(default="", max_length=20)
    display_unit: str = Field(default="", max_length=20)
    choices: list[str] = Field(default_factory=list)
    help: str | None = None
    sort_order: int = 0


class ConditionKeyUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    dimension: str | None = Field(default=None, max_length=30)
    si_unit: str | None = Field(default=None, max_length=20)
    display_unit: str | None = Field(default=None, max_length=20)
    choices: list[str] | None = None
    help: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# --- 사양 정의 ---------------------------------------------------------------


class SpecGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    label: str
    description: str | None
    sort_order: int
    definition_count: int
    """이 그룹에 든 사양 수. **지우기 전에 보여 준다** — 빈 줄로 보이는 그룹을
    지웠는데 뒤에 스무 개가 매달려 있는 일이 없어야 한다."""


class SpecGroupCreateRequest(BaseModel):
    slug: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    label: str = Field(min_length=1, max_length=100)
    description: str | None = None
    sort_order: int = 0


class SpecGroupUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    sort_order: int | None = None


class SpecDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    label: str
    group_id: uuid.UUID
    group_slug: str
    group_label: str
    kind: str
    dimension: str
    si_unit: str
    display_unit: str
    choices: list[str]
    condition_key_id: uuid.UUID | None
    condition_label: str | None
    """이은 검색축의 이름. **비어 있으면 이 사양은 검색에 안 걸린다** — 대부분이
    그렇고, 그래도 된다(ADR 0005)."""
    reflect_as: str
    help: str | None
    sort_order: int
    is_active: bool

    category_term_ids: list[uuid.UUID]
    categories: list[str]
    """붙는 장비 분류. **비어 있으면 공통**이다 — "아직 안 정했음" 이 아니다."""
    usage_count: int
    """이 사양으로 적힌 값의 수. 끄거나 고치기 전에 보여 준다."""


class SpecDefinitionCreateRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,59}$")
    label: str = Field(min_length=1, max_length=150)
    group_id: uuid.UUID
    kind: str = Field(default="number", pattern="^(number|range|choice|boolean|text)$")
    dimension: str = Field(default="", max_length=30)
    si_unit: str = Field(default="", max_length=20)
    display_unit: str = Field(default="", max_length=20)
    choices: list[str] = Field(default_factory=list)
    condition_key_id: uuid.UUID | None = None
    reflect_as: str = Field(default="max", pattern="^(max|min)$")
    help: str | None = None
    sort_order: int = 0
    category_term_ids: list[uuid.UUID] = Field(default_factory=list)
    """비워 두면 모든 분류에 뜬다. **그것이 기본값이다** — 분류를 고르는 것은
    "이건 저 장비에만 있다" 를 아는 사람만 하면 된다."""


class SpecDefinitionUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.** None 은 "안 바꿈" 이다."""

    label: str | None = Field(default=None, min_length=1, max_length=150)
    group_id: uuid.UUID | None = None
    dimension: str | None = Field(default=None, max_length=30)
    si_unit: str | None = Field(default=None, max_length=20)
    display_unit: str | None = Field(default=None, max_length=20)
    choices: list[str] | None = None
    condition_key_id: uuid.UUID | None = None
    reflect_as: str | None = Field(default=None, pattern="^(max|min)$")
    help: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    category_term_ids: list[uuid.UUID] | None = None
    """**보내면 통째로 바꾼다.** 빈 목록은 "공통으로 되돌린다" 이다 — 그래서 안
    보내는 것과 구별해야 한다."""
