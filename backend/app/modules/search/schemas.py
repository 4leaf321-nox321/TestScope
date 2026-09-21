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


class AccessoryOffer(BaseModel):
    """**부속을 붙이면 된다** — 무엇을, 어디까지, 우리가 갖고 있나.

    본체 사양으로는 안 되거나 모르는 조건에 챔버·노가 답할 때 온다. 「부속이 필요하다」 만
    말하면 사람은 어느 부속인지 찾으러 카탈로그를 뒤져야 하고, 대개 거기서 멈춘다.
    """

    series_id: uuid.UUID
    series_name: str
    model_id: uuid.UUID
    model_name: str
    """**기종을 짚는다.** 계열로 답하면 -70~300 °C 챔버 계열이 600 °C 도 된다고 말한다."""
    condition_range: str
    """그 부속이 내는 범위. -150 ~ 600 degC."""
    owned_units: int
    """이 부속 기종으로 등록된 보유 대수(내가 볼 수 있는 것). **0 이 아니면 살 것이
    아니라 옆에서 가져오면 되는 것이다.**"""
    relation: str
    """카탈로그가 적어 둔 관계. extends_temperature · compatible_accessory · fits_on."""


class ConditionMatch(BaseModel):
    condition_key_id: uuid.UUID
    condition_label: str
    display_unit: str
    verdict: str
    """met · accessory · unmet · unknown.

    unknown 을 met 과 섞지 않는 것이 이 화면의 핵심이다. "그 조건이 안 적혀
    있다" 와 "된다" 는 다르고, 둘을 같게 답하면 사람은 헛걸음을 한다.

    accessory 는 **범위는 맞는데 옵션 부속(챔버·노)이 있어야** 나오는 값이다. 두 갈래로
    나온다: 카탈로그가 항온조 옵션 기준으로 적은 값이거나(사양에 표시가 붙어 있다), 본체로는
    안 되는데 **붙는 부속이 그 조건을 대 주거나**(`accessory` 칸이 그 부속을 짚는다). 앞은
    「됨」 으로 답하면 갖고 있지도 않은 챔버를 전제로 하는 것이고, 뒤는 빠뜨리면 「그런 장비가
    없다」 가 된다. 그 대에 챔버가 실제로 있으면 사람이 그 표시를 끈다.
    """
    asked: str
    """사람이 읽을 물음. 80 degC 에서 · 20 kN 이상."""
    condition_range: str | None
    """장비가 적어 둔 범위. -70 ~ 300 degC. 없으면 None."""
    reason: str | None = None
    """`unknown` 일 때 **왜 모르는지.** 「모른다」 만 말하면 사람은 채울 자리를 못 찾는다.

        missing   그 조건이 아예 안 적혀 있다
        no_range  적혀 있는데 양쪽 다 비어 있다(또는 글자 조건인데 글자가 없다)
        no_max    상한이 없어 「이상」 을 판정할 수 없다
        no_min    하한이 없어 「이하」 를 판정할 수 없다
    """
    accessory: AccessoryOffer | None = None
    """`accessory` 판정을 만든 부속. **본체가 못 대는 조건을 이것이 댄다** — 어느 기종인지,
    어디까지 되는지, 우리가 갖고 있는지까지. 사양에 붙은 옵션 표시로 `accessory` 가 된
    경우에는 비어 있다(무엇을 달아야 하는지가 카탈로그에 안 적혀 있다)."""


class SearchDiagnosis(BaseModel):
    """「없습니다」 를 **왜** 로 바꾸는 수들. 조건에 걸려 빠진 것, 아예 안 적힌 것,
    카탈로그에만 있는 것은 할 일이 다르다 — 앞은 조건을 넓히는 일, 가운데는 채우는 일,
    뒤는 사는 일이다."""

    equipment_with_item: int
    """이 시험 항목이 적힌 보유 장비 수(조건을 보기 전). 0 이면 「그 시험을 하는 장비가 등록된
    적이 없다」 — 조건이 좁은 것이 아니다."""
    catalog_series_with_item: int
    """이 시험 항목을 하는 카탈로그 계열 수. 보유는 0 인데 이것이 0 이 아니면 「사면
    된다」 다."""
    unlinked_equipment: int
    """기종에 안 이어진 보유 장비 수(내가 보는 것). 그 장비들은 카탈로그 시험 항목을 못 받아
    검색에 안 걸린다 — 그중에 답이 숨어 있을 수 있다."""


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
    """match · accessory · partial · unknown.

    accessory — 조건은 다 맞지만 그중 하나 이상이 옵션 부속 기준이다.

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
    diagnosis: SearchDiagnosis | None = None
    """시험 항목(또는 물성)으로 물었을 때 — 결과가 왜 이런지 가르는 수들."""
    expanded_test_items: list[str] = []
    """물성으로 물었을 때 어느 시험 항목들로 펼쳤나. **비어 있으면 그 물성을 내는 시험이
    아직 안 이어진 것**이다 — 결과 0 건이 「장비가 없다」 가 아니라 「연결이 없다」 라는
    말을 화면이 할 수 있어야 한다."""


class CatalogModelHit(BaseModel):
    """기종 하나의 판정. **기종 단위다** — 수치가 갈리는 자리가 기종이라(ADR 0006), 계열로
    답하면 0.5 kN 짜리 한 대를 가진 부서가 「300 kN 됩니까」 에 된다고 답한다."""

    model_id: uuid.UUID
    model_name: str
    verdict: str
    """match · accessory · partial · unknown. 장비 검색과 같은 말이다."""
    conditions: list[ConditionMatch]
    owned_units: int
    """이 기종으로 등록된 보유 장비 수(내가 볼 수 있는 것). **사기 전에 보는 숫자다** —
    이미 있는 것을 또 사는 일이 이 시스템이 막으려는 것 중 하나다."""


class CatalogHit(BaseModel):
    """계열 하나 — 무슨 시험이 되나는 계열이 말하고, 어디까지 되나는 그 안의 기종이 말한다."""

    series_id: uuid.UUID
    series_name: str
    maker: str | None
    category: str | None
    test_item: str
    methods: list[str]
    """이 계열이 그 시험 항목에 인용한 규격 번호들."""
    note: str | None
    models: list[CatalogModelHit]
    """조건에 걸려 빠진 기종은 없다. 하나도 안 남으면 계열도 안 온다."""


class CatalogSearchResponse(BaseModel):
    """「이 시험을 하려면 어떤 기종이 되나 / 사야 하나」 의 답.

    장비 검색이 **우리가 가진 것**을 답한다면 이것은 **세상에 있는 것**을 답한다. 둘을 한
    화면에 두는 이유: 가진 것이 없을 때 다음 물음은 늘 「그러면 무엇을 사나」 다.
    """

    hits: list[CatalogHit]
    total_series: int
    total_models: int
    unmet_models: int
    """조건에 걸려 빠진 기종 수. 0 건일 때 「없어서」 와 「조건이 좁아서」 를 가른다."""
    expanded_test_items: list[str] = []


class SemanticHit(BaseModel):
    """뜻이 가까운 것 하나."""

    kind: str
    """test_item · property · series · model · method · equipment · reliability_test"""
    id: str
    title: str
    snippet: str
    """카드의 앞부분 — 왜 걸렸는지 사람이 보는 자리."""
    score: float
    """0~1. 코사인 유사도. bge-m3 실측으로 0.5 위가 맞는 것, 0.4 안팎은 우연이다."""


class SemanticSearchResponse(BaseModel):
    """의미 검색 — **글자가 안 겹쳐도 뜻이 가까우면** 찾는다.

    구조화 검색(`/search/test-items`)의 **앞자리**다: 「열충격 500사이클 되는 챔버」 같은
    자유 문장에서 시험 항목·계열 후보를 뽑고, 그다음은 사슬(시험 항목 → 조건 → 장비)이
    답한다. 벡터가 장비를 직접 답하지 않는다. 부품(pgvector·Ollama)이 없으면 `available`
    이 false 이고 결과는 빈 목록이다 — 오류가 아니다.
    """

    available: bool
    hits: list[SemanticHit]
