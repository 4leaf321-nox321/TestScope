"""장비 찾기의 요청·응답 형태.

    "80도 환경에서 20 kN 이상의 인장시험 가능한 장비 있어?"

이 한 문장이 셋으로 갈라진다: 시험 항목(인장), 조건 하나는 **그 값에서**(80도),
조건 하나는 **그 값 이상**(20 kN). 셋을 한 종류로 뭉치면 답이 틀린다 — 80도는
구간 안에 들어야 하고, 20 kN 은 장비의 상한이 그보다 커야 한다.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ConditionQuery(BaseModel):
    """조건 하나에 대한 물음.

    **셋 중 하나만 채운다.** 여러 개를 채우면 서로 다른 물음이 한 줄에 섞인다.
    값은 SI 로 보낸다 — 화면이 조건 정의의 si_unit 을 보고 환산한다.
    """

    condition_key_id: uuid.UUID

    at: float | None = None
    """그 값에서 되나. 80도 환경 — 장비의 [min, max] 안에 들어야 한다."""

    at_least: float | None = None
    """그 값 이상 되나. 20 kN 이상 — 장비의 max 가 그보다 커야 한다.
    max 가 비어 있으면 상한이 없다는 뜻이므로 **통과**다."""

    at_most: float | None = None
    """그 값 이하로 내려가나. -40도까지 — 장비의 min 이 그보다 작아야 한다."""

    text: str | None = Field(default=None, max_length=200)
    """choice·boolean 조건의 값."""


class SearchRequest(BaseModel):
    test_item_term_id: uuid.UUID | None = None
    property_term_id: uuid.UUID | None = None
    """물성으로 묻는다 — 「인장강도 재는 장비」. 그 물성을 내는 시험 항목 **전부**로
    펼쳐서 찾는다(N:M). 시험 항목까지 함께 주면 그 안에서 그 항목만 본다."""
    method_id: uuid.UUID | None = None
    """규격까지 지정하면 그 규격을 걸어 둔 시험 항목만 완전 일치로 본다."""
    conditions: list[ConditionQuery] = Field(default_factory=list, max_length=20)

    include_unavailable: bool = False
    """점검·수리·폐기 중인 장비도 볼까.

    기본은 뺀다 — **오늘 시험을 잡을 수 없는 장비를 가능하다고 답하면**, 그 답을
    믿고 일정을 짠 사람이 막힌다. 다만 "우리 조직이 원래 할 수 있는 시험인가" 를
    묻는 사람도 있으므로 손잡이는 남긴다.
    """
    workspace_slug: str | None = None
    site_term_id: uuid.UUID | None = None
    """거점으로 좁힌다. **가려면 이동해야 하는 단위**라 실무에서 가장 먼저 묻는다."""


class ConditionMatch(BaseModel):
    condition_key_id: uuid.UUID
    condition_label: str
    display_unit: str
    verdict: str
    """met · unmet · unknown.

    unknown 을 met 과 섞지 않는 것이 이 화면의 핵심이다. "그 조건이 안 적혀
    있다" 와 "된다" 는 다르고, 둘을 같게 답하면 사람은 헛걸음을 한다.
    """
    asked: str
    """사람이 읽을 물음. 80 degC 에서 · 20 kN 이상."""
    condition_range: str | None
    """장비가 적어 둔 범위. -70 ~ 300 degC. 없으면 None."""


class SearchHit(BaseModel):
    equipment_test_item_id: uuid.UUID
    equipment_id: uuid.UUID
    asset_no: str
    equipment_name: str
    status: str
    workspace_name: str | None
    site: str | None
    location: str | None
    contact_name: str | None
    """**찾은 다음에 연락할 사람.** 없으면 검색은 절반만 한 것이다."""

    test_item: str
    method_code: str | None
    confidence: str
    note: str | None

    verdict: str
    """match · partial · unknown.

      match    물은 조건이 전부 충족된다
      partial  일부는 충족되고 일부는 **모른다**(장비에 그 조건이 안 적혀 있다)
      unknown  물은 조건 중 아는 것이 하나도 없다

    안 되는 것(unmet)은 아예 결과에서 뺀다 — 그것은 답이 아니라 소음이다.
    """
    conditions: list[ConditionMatch]
    calibration_due_on: str | None
    """교정 예정일. 지났으면 화면이 표를 단다 — **말 안 하면 사람은 만료된
    장비로 시험을 잡는다.**"""


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    total: int
    unmet_count: int
    """조건에 걸려 빠진 시험 항목 수. **0 건일 때 이 숫자가 답을 준다** — 아무것도 안
    나온 것이 "그런 장비가 없어서" 인지 "조건이 너무 좁아서" 인지 가른다."""
    unregistered_equipment: int
    """시험 항목이 하나도 안 적힌 장비 수. 검색에 절대 안 걸리는 것들이라, 결과가
    빈약할 때 **어디를 채워야 하는지**를 말해 준다."""
    expanded_test_items: list[str] = []
    """물성으로 물었을 때 어느 시험 항목들로 펼쳤나. **비어 있으면 그 물성을 내는 시험이
    아직 안 이어진 것**이다 — 결과 0 건이 「장비가 없다」 가 아니라 「연결이 없다」 라는
    말을 화면이 할 수 있어야 한다."""
