"""온톨로지 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import Request


class AttributeField(Request):
    key: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="text", pattern="^(text|number|list)$")
    help: str | None = Field(default=None, max_length=300)


class VocabularyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    label: str
    domain: str
    """어디의 축인가 — `equipment` · `catalog` · `method` · `common`.

    화면이 이것으로 묶는다. 한 목록에 일곱이 나란히 서면 「이게 어디 쓰이는 값이지」 를
    알 수 없고, 그때 제정기관 축에 회사 이름이 들어간다."""
    domain_label: str
    description: str | None
    entry_policy: str
    parent_slug: str | None
    sort_order: int
    attribute_schema: list[AttributeField]
    """값이 갖는 칸의 정의. 편집 화면이 이것을 보고 칸을 그린다."""
    term_count: int
    """값이 몇 개인가. **축 목록에서 이걸 못 보면** 비어 있는 축과 채워진 축이
    같아 보이고, 어디를 채워야 하는지 알 수 없다."""


class VocabularyCreateRequest(Request):
    """축 하나를 새로 세운다. **slug 는 코드가 거는 이름**이라 만든 뒤 못 바꾼다.

    `domain` 은 화면이 축을 묶는 자리다 — 안 고르면 `common` 이 되는데, 그것은 얼버무리는
    자리가 아니라 **정말 여러 층이 쓰는 축**을 뜻한다. 보유 장비만 쓰는 축이면 `equipment`
    라고 적는 편이 목록에서 찾기 쉽다.
    """

    slug: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    label: str = Field(min_length=1, max_length=100)
    domain: str = Field(default="common", pattern="^(equipment|catalog|method|common)$")
    description: str | None = None
    entry_policy: str = Field(default="open", pattern="^(open|closed)$")
    parent_slug: str | None = Field(default=None, max_length=50)
    """계층이 있는 축에서 위 축의 slug. 장비 분류의 군 → 유형이 그렇다."""
    sort_order: int = 0
    attribute_schema: list[AttributeField] = Field(default_factory=list)


class VocabularyUpdateRequest(Request):
    """축을 고친다. **slug 와 소속은 못 바꾼다** — 코드가 걸고 있다.

    정책을 open 에서 closed 로 바꾸는 것은 된다: 값이 흩어지기 시작한 축을 잠그는 일이
    실제로 있다. 반대도 된다 — 다만 그 축이 검색의 첫 축이면 오타가 값이 된다."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    entry_policy: str | None = Field(default=None, pattern="^(open|closed)$")
    attribute_schema: list[AttributeField] | None = None


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


class TermCreateRequest(Request):
    value: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=120)
    parent_term_id: uuid.UUID | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TermUpdateRequest(Request):
    """**안 보낸 것과 비운 것을 구별한다.**

    None 은 "안 바꿈" 이다. 구별하지 않으면 이름 하나 고칠 때마다 코드와 상위 값이
    조용히 지워진다 — 그 손실은 저장 버튼을 누른 사람 눈에 안 보인다.
    """

    value: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=120)
    parent_term_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|deprecated)$")
    attributes: dict[str, Any] | None = None


class TermMergeRequest(Request):
    """이 값을 다른 값으로 합친다. 원본은 별칭이 되어 남는다.

    **지우지 않고 별칭으로 남기는 이유**: 같은 오타가 또 들어오는 것을 막는다.
    사후에 합치는 것보다 애초에 안 생기게 하는 것이 싸다.
    """

    target_term_id: uuid.UUID


class AliasCreateRequest(Request):
    value: str = Field(min_length=1, max_length=200)


class ReferenceRowOut(BaseModel):
    """이 값을 가리키는 줄 하나 — 계열·장비·규격·연결."""

    id: uuid.UUID
    label: str
    href: str | None
    """화면 주소. 없으면 갈 화면이 없는 것(사양 출처)."""


class ReferenceGroupOut(BaseModel):
    key: str
    label: str
    detach: str
    """delete(연결 줄을 지운다) · null(칸을 비운다) · none(못 뗀다 — 옮기기만)."""
    rows: list[ReferenceRowOut]


class ReferenceReassignRequest(Request):
    target_term_id: uuid.UUID


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
    """이 조건을 쓰는 시험 항목·요구 수. **끄거나 고치기 전에 보여 준다** — 단위를
    고치면 이미 저장된 그 숫자들의 뜻이 통째로 바뀐다."""


class ConditionKeyCreateRequest(Request):
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


class ConditionKeyUpdateRequest(Request):
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


class SpecGroupCreateRequest(Request):
    slug: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    label: str = Field(min_length=1, max_length=100)
    description: str | None = None
    sort_order: int = 0


class SpecGroupUpdateRequest(Request):
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


class SpecDefinitionCreateRequest(Request):
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


class SpecDefinitionUpdateRequest(Request):
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
