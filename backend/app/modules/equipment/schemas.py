"""장비 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CalibrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    calibrated_on: date
    next_due_on: date | None
    certificate_no: str | None
    provider: str | None
    note: str | None


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_no: str
    name: str

    model_id: uuid.UUID | None
    model_name: str | None
    """카탈로그의 기종명. **비어 있으면 카탈로그 미연결**이다 — 화면이 그것을
    표시한다. 빈 칸을 빈 칸으로 두면 아무도 안 채운다(ADR 0004)."""
    series_id: uuid.UUID | None
    series_name: str | None
    """그 기종이 속한 계열. 사람이 아는 이름은 대개 이쪽이다 — 「6800 시리즈」 는
    알아도 「68FM-300」 은 라벨을 봐야 안다(ADR 0006)."""
    category: str | None
    manufacturer: str | None
    """**모델에서 끌어온다.** 개체는 이 둘을 갖지 않는다 — 같은 모델 열 대에 열 번
    적히면 열 번 다 같을 이유가 없다.

    이름으로 주는 이유: id 만 주면 목록 한 줄을 그리려고 화면이 카탈로그를 또
    조회해야 하고, 그 조회가 빠진 화면은 빈 칸을 보여 준다."""

    serial_no: str | None
    workspace_slug: str | None
    workspace_name: str | None
    site: str | None
    location: str | None
    status: str
    acquired_on: date | None
    contact_name: str | None
    note: str | None
    capability_count: int
    """이 장비에 등록된 역량 수. 0 이면 **검색에 절대 안 걸린다** — 목록에서
    그것이 보여야 채워 넣을 마음이 생긴다."""
    test_items: list[str]
    """이 장비가 하는 시험 항목. **목록 한 줄에서 바로 보인다** — 역량을 열어 봐야
    아는 화면은 「우리가 무슨 시험을 할 수 있나」 에 답하지 못한다."""
    calibration_due_on: date | None
    """가장 최근 교정의 다음 예정일. 지났으면 화면이 표를 단다."""
    created_at: datetime
    can_edit: bool
    """요청한 사람이 고칠 수 있는가. **서버가 판정한다** — 화면이 스스로 계산하면
    화면마다 답이 달라진다."""


class EquipmentCreateRequest(BaseModel):
    asset_no: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    workspace_slug: str | None = None
    """비우면 전사 공용 — 시스템 관리자만 만들 수 있다."""

    model_id: uuid.UUID | None = None
    """카탈로그의 모델. **고르면 그 모델의 역량이 이 장비로 복사된다** — 상속이
    아니라 복사다(ADR 0004). 그 뒤로는 이 장비가 진실이고, 챔버를 뗐다면 여기서
    고친다.

    비울 수 있다. 자작 장비나 아직 카탈로그에 없는 것이 실제로 있고, 그때 등록을
    막으면 사람은 시스템 밖에서 일한다."""

    serial_no: str | None = Field(default=None, max_length=100)
    site_term_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=200)
    status: str = Field(default="operational")
    acquired_on: date | None = None
    contact_user_id: uuid.UUID | None = None
    note: str | None = None


class EquipmentUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.**

    부분 수정이라 None 은 "안 바꿈" 이다. 구별하지 않으면 상태 하나 바꿀 때마다
    담당자와 설치 위치가 지워지고, 그 손실은 저장한 사람 눈에 안 보인다.
    빈 문자열을 보내면 그것은 "비운다" 이다.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    model_id: uuid.UUID | None = None
    """카탈로그 연결을 바꾼다. **역량은 다시 복사되지 않는다** — 이미 이 장비의
    것이 된 값을 사양서로 덮으면, 손으로 고쳐 둔 실측이 조용히 사라진다."""
    serial_no: str | None = None
    site_term_id: uuid.UUID | None = None
    location: str | None = None
    status: str | None = None
    acquired_on: date | None = None
    contact_user_id: uuid.UUID | None = None
    note: str | None = None
    workspace_slug: str | None = None
    """다른 부서로 넘긴다. **넘기려면 양쪽 다 관리자여야 한다.**"""


class CalibrationCreateRequest(BaseModel):
    calibrated_on: date
    next_due_on: date | None = None
    certificate_no: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=200)
    note: str | None = None


# --- 카탈로그 ----------------------------------------------------------------


class ModelLimitOut(BaseModel):
    """계열 역량의 조건 한 칸. 개체 쪽(LimitOut)과 같은 모양이다."""

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


class ModelCapabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_item_term_id: uuid.UUID
    test_item: str
    method_id: uuid.UUID | None
    method_code: str | None
    note: str | None
    limits: list[ModelLimitOut]
    """**계열 전체가 만족하는 조건만** 여기 온다. 기종마다 갈리는 수치는 그 기종의
    사양에서 오고, 보유 장비를 만들 때 합쳐진다(ADR 0006)."""


class SeriesRelationOut(BaseModel):
    """계열에 붙은 관계 한 줄."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    relation: str
    other_series_id: uuid.UUID
    other_name: str
    other_maker: str | None
    other_kind: str
    note: str | None
    inbound: bool
    """이 계열이 관계의 **대상 쪽**인가. 챔버 화면에서 「이 챔버가 붙는 시험기들」 을
    보여 주려면 양방향이 다 필요하다 — 한쪽만 보여 주면 부속 화면이 늘 비어 있다."""


class EquipmentSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    name_ko: str | None
    maker: str | None
    maker_term_id: uuid.UUID | None
    brand: str | None
    category: str | None
    category_term_id: uuid.UUID | None
    kind: str
    """본체(main)인가 부속(accessory·sensor·software)인가."""
    drive: str
    form_factor: str
    status: str
    summary: str | None
    spec_note: str | None
    source_id: uuid.UUID | None
    source_path: str | None
    raw_limits: dict[str, Any]
    """계열 사양표 원문. 기종이 여럿이면 이 값은 **봉투**라 수치로 안 들이지만
    (ADR 0006), 사람이 읽을 값이라 원문을 남긴다."""

    model_count: int
    """이 계열에 든 기종 수. **0 이면 아무도 이 계열을 가리킬 수 없다** — 보유
    장비는 기종을 가리키기 때문이다."""
    unit_count: int
    operational_count: int
    """계열 전체의 보유 대수와 가동 대수. 기종별 수는 기종 목록이 갖는다."""

    capabilities: list[ModelCapabilityOut]
    relations: list[SeriesRelationOut]
    created_at: datetime
    can_edit: bool
    """카탈로그는 전사 공용이라 시스템 관리자만 고친다. **서버가 판정한다.**"""


class EquipmentSeriesCreateRequest(BaseModel):
    """계열을 만든다.

    **만들기 전에 `POST /api/resolve` 로 먼저 찾는다.** 같은 계열이 두 줄로 갈리면
    보유 장비가 어느 쪽을 가리켰는지에 따라 검색 결과가 나뉜다. 이미 있으면 409 가
    오고, `details.series_id` 에 그 id 가 실려 온다 — **409 는 실패가 아니라 답이다.**

    id 대신 이름을 줘도 된다(`maker` · `category`). 다만 그 이름이 기준정보에
    **하나로 정해질 때만** 받는다: 여럿이면 거절하고 후보를 돌려준다. 고르는 것은
    사람의 일이다.
    """

    name: str = Field(min_length=1, max_length=200)
    """계열 이름만 적는다. **제조사는 옆 칸이 갖는다** — 이름에 섞으면
    `Instron 6800` 과 `6800` 이 별개 계열로 갈린다."""
    name_ko: str | None = Field(default=None, max_length=200)
    maker_term_id: uuid.UUID | None = None
    maker: str | None = Field(default=None, max_length=200)
    """제조사를 **이름으로** 줄 때. id 가 있으면 id 가 이긴다.

    없는 제조사는 만들지 않는다 — 오타가 새 제조사가 되면 그 계열은 목록에서
    진짜 제조사들 사이에 혼자 선다."""
    brand: str | None = Field(default=None, max_length=100)
    category_term_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=200)
    """장비 분류를 **이름으로** 줄 때."""
    kind: str = Field(default="main", pattern="^(main|accessory|sensor|software)$")
    drive: str = Field(default="", max_length=30)
    form_factor: str = Field(default="", max_length=40)
    summary: str | None = None
    spec_note: str | None = None
    source_id: uuid.UUID | None = None


class EquipmentSeriesUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.** None 은 "안 바꿈" 이다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_ko: str | None = Field(default=None, max_length=200)
    maker_term_id: uuid.UUID | None = None
    brand: str | None = Field(default=None, max_length=100)
    category_term_id: uuid.UUID | None = None
    kind: str | None = Field(default=None, pattern="^(main|accessory|sensor|software)$")
    drive: str | None = Field(default=None, max_length=30)
    form_factor: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, pattern="^(active|discontinued)$")
    summary: str | None = None
    spec_note: str | None = None
    source_id: uuid.UUID | None = None


class SeriesRelationCreateRequest(BaseModel):
    part_series_id: uuid.UUID
    relation: str = Field(max_length=30)
    note: str | None = None
    """`-150 ~ +600 °C` 처럼 **무엇이 어떻게 바뀌는지**를 적는다."""


class EquipmentModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID
    series_name: str
    name: str
    name_ko: str | None
    maker: str | None
    maker_term_id: uuid.UUID | None
    category: str | None
    category_term_id: uuid.UUID | None
    """**계열에서 끌어온다.** 기종은 이 둘을 갖지 않는다 — 한 계열 열 기종에 열 번
    적히면 열 번 다 같을 이유가 없다.

    이름과 id 를 함께 주는 이유: 이름만으로는 사양 정의를 분류로 거를 수 없고,
    id 만으로는 목록 한 줄을 그리려고 화면이 기준정보를 또 조회해야 한다."""
    form_factor: str
    status: str
    summary: str | None
    spec_note: str | None
    raw_specs: dict[str, Any]
    """제조사 카탈로그의 **사양 원문 그대로.**

    정의로 세운 칸은 위 사양표가 갖는다. 여기에는 정의가 없는 것까지 전부 있다 —
    원본에 950종 넘는 키가 있고 대부분이 한 카탈로그에만 나온다. 정의로 세우면
    관리 화면이 죽고, 안 세우면 사라진다. **그래서 둘 다 한다.**

    화면은 이것을 접어서 보여 준다: 「카탈로그 원문」."""

    unit_count: int
    """이 기종을 몇 대 가졌나. **카탈로그가 답해야 하는 첫 물음이다.**"""
    operational_count: int
    """그중 지금 쓸 수 있는 것. 다섯 대 중 한 대만 가동이면 그 사실이 목록에
    보여야 한다 — 대수만 보면 여유 있어 보인다."""

    capabilities: list[ModelCapabilityOut]
    """**계열의 역량이다.** 이 기종만의 것이 아니라 계열이 하는 시험 목록이고,
    조건은 이 기종의 사양이 좁힌다(ADR 0006)."""
    created_at: datetime
    can_edit: bool


class EquipmentModelCreateRequest(BaseModel):
    """기종을 만든다. **계열이 먼저 있어야 한다.**

    `series_id` 대신 `series`(계열 이름)를 줘도 된다. 제조사를 함께 주면 같은
    이름의 계열이 여럿일 때 하나로 좁혀진다.
    """

    series_id: uuid.UUID | None = None
    """**결국 비울 수 없다.** 단품이면 기종 하나짜리 계열을 먼저 만든다 — 예외를
    두면 화면이 매번 갈래를 타야 하고, 한 곳에서 빠뜨리면 그 기종이 목록에서
    사라진다. id 를 안 주면 `series` 이름으로 찾는다."""
    series: str | None = Field(default=None, max_length=200)
    """계열을 **이름으로** 줄 때. 하나로 정해지지 않으면 거절하고 후보를 준다."""
    maker: str | None = Field(default=None, max_length=200)
    """`series` 로 찾을 때 제조사까지 주면 후보가 줄어든다."""
    name: str = Field(min_length=1, max_length=150)
    name_ko: str | None = Field(default=None, max_length=150)
    form_factor: str = Field(default="", max_length=40)
    summary: str | None = None
    spec_note: str | None = None


class EquipmentModelUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.** None 은 "안 바꿈" 이다."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    name_ko: str | None = Field(default=None, max_length=150)
    series_id: uuid.UUID | None = None
    """계열을 옮긴다. **역량은 다시 복사되지 않는다** — 이미 등록된 장비의 값은
    그 장비가 갖는다."""
    form_factor: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, pattern="^(active|discontinued)$")
    summary: str | None = None
    spec_note: str | None = None


class ModelCapabilityCreateRequest(BaseModel):
    """이 계열이 무슨 시험을 하나.

    시험 항목은 **닫힌 축**이라 없는 이름은 안 받는다 — 오타가 값이 되면 그 계열의
    장비는 영영 검색에 안 걸린다.
    """

    test_item_term_id: uuid.UUID | None = None
    test_item: str | None = Field(default=None, max_length=200)
    """시험 항목을 **이름으로** 줄 때. 별칭도 본다 — 「UTM」 으로 물으면
    「만능재료시험기」 가 나온다."""
    method_id: uuid.UUID | None = None
    method_code: str | None = Field(default=None, max_length=100)
    """시험법을 **규격 번호로** 줄 때. `ASTM E8/E8M`."""
    note: str | None = None


class ModelLimitUpsertRequest(BaseModel):
    """조건 한 칸을 넣거나 덮어쓴다. 개체 쪽과 같은 규칙이다 —
    **비운 쪽은 "제한 없음"** 이고 0 이 아니다."""

    condition_key_id: uuid.UUID
    min_value: float | None = None
    max_value: float | None = None
    text_value: str | None = Field(default=None, max_length=200)
    note: str | None = None


# --- 모델 사양 ---------------------------------------------------------------


class ModelSpecValueOut(BaseModel):
    """사양 한 칸의 값. **정의의 계약을 함께 실어 준다.**

    화면이 이 값을 그리려면 단위와 종류를 알아야 하고, 그것을 따로 조회하게 하면
    조회를 빠뜨린 화면이 단위 없는 숫자를 보여 준다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    definition_id: uuid.UUID
    key: str
    label: str
    kind: str
    si_unit: str
    display_unit: str
    choices: list[str]
    sort_order: int
    is_active: bool
    """정의가 꺼졌어도 이미 적힌 값은 보여 준다 — 안 보이면 지워진 줄 안다."""
    condition_key_id: uuid.UUID | None
    """채워져 있으면 이 값이 역량 조건으로 따라 들어간 사양이다."""
    applies: bool
    """이 모델의 분류에 붙는 사양인가. **false 라도 값은 준다** — 분류를 나중에
    고쳤다고 이미 적은 사양이 사라지면 안 된다(ADR 0005)."""

    num_value: float | None
    num_min: float | None
    num_max: float | None
    text_value: str | None
    bool_value: bool | None
    note: str | None
    source_id: uuid.UUID | None
    source_path: str | None
    source_page: int | None
    updated_at: datetime


class ModelSpecGroupOut(BaseModel):
    group_id: uuid.UUID
    slug: str
    label: str
    description: str | None
    items: list[ModelSpecValueOut]


class ModelSpecSheetOut(BaseModel):
    """모델에 **적힌** 사양만 담는다.

    빈 칸 목록은 `/spec-definitions?category_term_id=…` 가 준다. 여기에 다 실으면
    한 모델을 열 때마다 수백 줄이 오가고, 그 대부분은 회색으로 그려진다.
    """

    model_id: uuid.UUID
    groups: list[ModelSpecGroupOut]


class ModelSpecValueUpsertRequest(BaseModel):
    """사양 한 칸을 넣거나 덮어쓴다.

    **종류에 맞는 칸만 채운다.** 나머지는 안 보내면 되고, 서버가 그것을 비운다 —
    남겨 두면 화면마다 어느 칸을 읽느냐에 따라 다른 값이 보인다.
    """

    definition_id: uuid.UUID
    num_value: float | None = None
    num_min: float | None = None
    num_max: float | None = None
    text_value: str | None = None
    bool_value: bool | None = None
    note: str | None = None
    """수치로 못 담는 단서. "챔버 장착 시" · "1상/3상에 따라 다름"."""
    source_id: uuid.UUID | None = None
    source_page: int | None = Field(default=None, ge=1)


class ModelSpecSaveResult(BaseModel):
    """저장 결과. **이 값이 검색에 쓰이는지, 이미 등록된 장비는 어떻게 되는지.**

    "저장했습니다" 만 말하면 둘 다 사람이 알 수 없다. 그리고 둘 다 모르면 사람은
    바뀌었다고 믿는데, 그 믿음은 검색 결과가 어긋난 날에야 깨진다.
    """

    value: ModelSpecValueOut
    search_axis: str | None
    """이어진 검색축의 이름. 채워져 있으면 **이 기종으로 앞으로 등록할 장비**의
    역량 조건이 된다. 비어 있으면 사양표에만 남는다 — 대부분이 그렇고 그래도 된다."""
    existing_units: int
    """이 기종으로 **이미 등록된** 보유 장비 수. 그들에게는 반영되지 않는다 —
    개체의 값은 개체가 갖는다(ADR 0004)."""


class SpecSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    title: str | None
    maker: str | None
    pages: int | None
    published_on: date | None
