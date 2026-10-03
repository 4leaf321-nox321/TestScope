"""신뢰성 시험 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.attributes.schemas import AttributeValueIn, AttributeValueOut
from app.modules.search.schemas import SearchHit
from app.shared.schemas import Request


class ReliabilityTestItemOut(BaseModel):
    """이 시험이 쓰는 시험 항목 하나와, 그 항목을 할 수 있는 **이 부서의** 장비 수."""

    term_id: uuid.UUID
    value: str
    equipment_count: int
    """**이 사업부 장비** 중 이 시험 항목이 되는 것. 내가 볼 수 있는 것만 센다 — 검색과
    같은 규칙. 0 이면 시험은 정해졌는데 돌릴 장비가 이 사업부에 없다는 뜻이다.

    사업부에 속한 부서 전부의 장비를 센다(조직도를 타고 내려간다) — 시험이 사업부의
    것이 된 뒤로 「이 팀에 없다」 는 답이 되지 않는다."""


class ReliabilityRejectRequest(Request):
    reason: str = Field(min_length=1, max_length=500)
    """왜 아닌가. **받아 둬야** AI 가 무엇을 자주 틀리는지 셀 수 있고, 같은 것을 또
    올리는지 안다 — 계정 거절이 사유를 받는 것과 같은 이유다."""


class ReliabilityBulkRequest(Request):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    """고른 줄들. 한 번에 500건까지 — 몇천 건은 나눠 누른다."""
    action: Literal["confirm", "reject", "delete", "reopen"]
    """`reopen` 은 **확정을 푸는 것**이다 — 그 순간부터 AI 가 다시 채울 수 있다."""
    reason: str | None = Field(default=None, max_length=500)
    """`reject` 와 `reopen` 일 때 **필수**다.

    한 건씩 누를 때는 그 자리에서 보고 누르는 것이라 안 받지만, 서른 건이 한꺼번에
    풀리면 반년 뒤에 「왜 풀렸나」 를 묻는 사람이 반드시 있다 — 그때 감사에 「누가
    열었나」 만 있으면 답할 수 없다."""


class ReliabilityBulkOut(BaseModel):
    """줄마다의 결과. **전부 되거나 전부 안 되거나로 두지 않는다** — 오백 줄 중 하나가
    남의 사업부라고 사백구십구 줄이 함께 막히면 쓸 수가 없다."""

    requested: int
    done: list[uuid.UUID]
    failed: list[dict[str, str]]
    """안 된 줄과 **왜**. 「12건 실패」 만으로는 다시 누를지 고칠지 알 수 없다."""


class DivisionOut(BaseModel):
    """사업부 하나 — 사이드바와 등록 창이 쓴다."""

    code: str
    name: str
    can_register: bool
    """내가 이 사업부에 시험을 올릴 수 있나. **줄마다 말한다** — 못 고를 것을 숨기면
    「왜 우리 사업부가 없지」 가 되고, 표시 없이 보이면 다 적고 나서 거절당한다."""


class ReliabilityTestOut(BaseModel):
    id: uuid.UUID
    division_code: str
    """사업부의 코드(`mx`·`vd`…). 주소와 코드가 거는 키라 이름이 바뀌어도 안 깨진다."""
    division_name: str
    name: str
    purpose: str
    document_revision_id: uuid.UUID | None = None
    """이 줄이 속한 규격서의 판. **판마다 한 벌**이라 같은 이름이 판마다 따로 선다."""
    document_revision_label: str | None = None
    """그 판의 이름(「18」·「Rev.3」) — id 만 오면 사람이 못 읽는다."""
    status: str = "confirmed"
    """`candidate`(후보) · `confirmed`(확정). **후보는 AI 가 올리고 아직 사람이 안 본
    것이다** — 화면이 배지를 달고, 확인 전에는 전사 목록에 안 낸다."""
    submitted_via: str | None = None
    """후보를 올린 통로 — PAT 이름. 검토하는 사람이 「이거 누가 올린 거야」 에 바로 답한다."""
    confirmed_by: str | None = None
    """확인한 사람의 이름. **「이 값 누가 보증했어」 의 답이다.**"""
    confirmed_at: datetime | None = None
    test_items: list[ReliabilityTestItemOut]
    attributes: list[AttributeValueOut]
    """항목 값 — 정식이 먼저, 초안이 뒤. `status` 로 가른다."""
    attachment_count: int = 0
    """붙은 그림 수. **목록이 낱장을 받지 않는다** — 줄마다 그림을 받아 오면 스무 줄에
    쉰 번을 왕복한다. 수만 보이고, 누르면 그때 받는다."""
    can_edit: bool
    """요청한 사람이 고칠 수 있나 — **그 사업부에 속한 부서의 관리자** 또는 시스템
    관리자. 화면이 단추를 보일지 정하는 데 쓴다. 판정은 서버가 한다."""
    created_at: datetime
    updated_at: datetime


class ReliabilityTestCreateRequest(Request):
    division_code: str
    """어느 사업부의 시험인가. 내 소속(관리자 역할)이 속한 사업부만 받는다 —
    시스템 관리자는 전부."""
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(default="", max_length=4000)
    document_revision_id: uuid.UUID | None = None
    """이 시험이 **규격서의 어느 판**의 것인가. 판마다 한 벌을 둔다 — 개정 14와 18의 같은
    이름은 서로 다른 시험이고, 이 칸이 그것을 가른다."""
    test_item_term_ids: list[uuid.UUID] = Field(default_factory=list)
    attributes: list[AttributeValueIn] = Field(default_factory=list)
    """항목 값. `definition_id` 가 없고 `new_label` 이 있으면 초안 항목이 생긴다."""


class ReliabilityTestBatchItem(Request):
    """묶음 안의 한 줄. `division_code` 는 묶음이 갖는다."""

    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(default="", max_length=4000)
    document_revision_id: uuid.UUID | None = None
    """줄이 제 판을 적으면 **묶음이 준 판을 안 덮는다** — 한 묶음에 두 판이 섞이는 일이
    실제로 있다(개정 18에서 안 바뀐 시험은 14의 판으로 남긴다)."""
    test_item_term_ids: list[uuid.UUID] = Field(default_factory=list)
    attributes: list[AttributeValueIn] = Field(default_factory=list)


class ReliabilityBatchRequest(Request):
    """문서 하나에서 뽑은 시험들을 **한 번에** 올린다.

    AI 가 규격서 한 권에서 시험 스무 건을 뽑는다. 한 건씩 스무 번 부르면 중간에 열 번째가
    막혔을 때 **앞의 아홉은 이미 들어가 있고** 뒤의 열은 없다 — 무엇이 올라갔는지 부른 쪽도
    사람도 모른다. 그리고 그 스무 건이 한 문서에서 나왔다는 사실이 어디에도 안 남는다.
    """

    division_code: str
    """줄마다 다시 적지 않는다 — 한 문서는 한 사업부의 것이다."""
    document_id: uuid.UUID | None = None
    """어느 사내 규격서에서 뽑았나. **주면 줄마다 「규격서」 칸에 걸린다** — 그래야 사람이
    문서 단위로 모아 보고, 값이 틀렸을 때 원본으로 되짚는다. 줄이 제 `attributes` 에
    규격서를 이미 적었으면 그것을 안 덮는다."""
    document_revision_id: uuid.UUID | None = None
    """어느 **판**의 것인가. `document_id` 와 같은 방식으로 **줄마다 걸린다.**

    판마다 줄이 서므로, 개정 14를 올린 뒤 개정 18을 올릴 때는 이 칸만 바꿔 같은 이름을
    다시 올린다 — 그 둘은 서로 다른 줄이고, 목록은 최신판만 보여 준다.

    **규격서를 줬으면 판도 줘야 한다.** 판 없이 올리면 같은 자리에 쌓여 뒤엣것이 앞엣것을
    조용히 덮는다 — 운영에서 1509건이 판 없이 들어갔고 그 길로 값이 사라졌다."""
    tests: list[ReliabilityTestBatchItem] = Field(min_length=1, max_length=500)
    """한 번에 500건까지 — `ReliabilityBulkRequest` 와 같은 상한이다."""


class ReliabilityMergeOut(BaseModel):
    """**이미 있던 줄에 다시 올린 결과** — 무엇을 어떻게 했는지.

    예전에는 `merged` 로 세기만 했다. 보낸 값이 반영이 안 돼도 성공처럼 보였고, 운영에서
    36건의 값이 그렇게 조용히 사라졌다(2026-10-01). 세는 것과 **한 일을 말하는 것**은
    다르다.
    """

    test: ReliabilityTestOut
    action: str
    """`updated` 바꿨다 · `skipped` 바뀐 것이 없다."""
    changed: list[str] = []
    """**덮어쓴 칸의 이름.** 「시험 온도」 「시험 시간(불량 시)」 — 그 칸의 옛 값은 이
    판에서 사라졌다. 다른 판의 값은 그대로다."""
    reason: str | None = None
    """`skipped` 일 때 왜."""


class ReliabilityBatchOut(BaseModel):
    """줄마다의 결과 — **전부 되거나 전부 안 되거나로 두지 않는다.**

    스무 줄 중 하나가 이름이 겹친다고 열아홉이 함께 막히면, 부른 쪽은 그 하나를 고치려고
    스무 줄을 다시 보낸다. 그러다 하나를 빠뜨린다.
    """

    requested: int
    created: list[ReliabilityTestOut]
    merged: list[ReliabilityMergeOut] = []
    """**같은 판을 다시 올린 것.** 판이 줄의 자리가 된 뒤로(0049) 개정 18은 14의 줄에
    안 붙는다 — 붙였더니 14의 값이 사라졌다. 여기 오는 것은 같은 판의 재적재이고, 줄마다
    무엇을 덮었는지가 함께 온다."""
    failed: list[dict[str, str]]
    """안 된 줄과 **왜**. `name` 이 함께 온다 — id 가 없는 줄이라 그것 말고는 가리킬 것이
    없다."""


class ReliabilityTestUpdateRequest(Request):
    """안 보낸 칸은 그대로. `test_item_term_ids` 는 보내면 **통째로** 바뀐다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = Field(default=None, max_length=4000)
    document_revision_id: uuid.UUID | None = None
    """판을 옮긴다. 보내면 이름 유일성의 자리도 함께 바뀐다."""
    test_item_term_ids: list[uuid.UUID] | None = None
    attributes: list[AttributeValueIn] | None = None
    """보내면 통째로 바뀐다 — 시험 항목과 같은 규칙."""


class TestItemProposalOut(BaseModel):
    """축에 맞는 값이 없어 남긴 제안 한 줄."""

    id: uuid.UUID
    text: str
    """문서에 적힌 그대로 — 「염수분무(5%)」."""
    note: str | None
    """왜 축에서 못 찾았는지."""
    status: str
    """`open` · `linked` · `created` · `rejected`."""
    reliability_test_id: uuid.UUID
    reliability_test_name: str
    term_id: uuid.UUID | None
    term_value: str | None
    submitted_via: str | None
    created_at: datetime


class TestItemProposalGroupOut(BaseModel):
    """같은 말끼리 모은 한 줄 — **관리자는 스무 번이 아니라 한 번 판단한다.**"""

    normalized: str
    text: str
    count: int
    """이 말을 낸 시험 수. **큰 것이 먼저** — 스무 시험에서 나온 말은 축에 없는 것이 거의
    확실하고, 한 번 나온 말은 오타일 수 있다."""
    proposals: list[TestItemProposalOut]


class TestItemProposalRequest(Request):
    reliability_test_id: uuid.UUID
    text: str = Field(min_length=1, max_length=200)
    """문서에 적힌 그대로. **고쳐 쓰지 마라** — 판단하는 사람이 원문을 봐야 한다."""
    note: str | None = Field(default=None, max_length=2000)


class TestItemProposalDecision(Request):
    """정하기 — 기존 값에 잇거나(`term_id`), 축에 세우거나(`new_value`), 아니라고 하거나
    (`reject`). **셋 중 하나만.**"""

    normalized: str = Field(min_length=1, max_length=200)
    term_id: uuid.UUID | None = None
    new_value: str | None = Field(default=None, min_length=1, max_length=200)
    reject: bool = False
    """아니라고 한다. 빈 본문을 거절로 읽으면 인자를 빠뜨린 호출(AI 가 term_id 를 잊은 것)이
    조용히 요청을 닫는다 — 기종 등록 요청과 같은 규칙이다."""


class RevisionBriefOut(BaseModel):
    id: uuid.UUID
    label: str
    test_count: int


class RevisionTestBriefOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str


class RevisionDifferenceOut(BaseModel):
    """조건 한 자리가 어떻게 바뀌었나."""

    at: str
    """자리 — `칸key@묶음#차례`. **정의 id 가 아니라 key 다**: 판마다 다른 초안이 끼면
    id 로는 전부 「바뀜」 이 된다."""
    before: str | None
    after: str | None
    """사람이 읽는 글자로 견준다. 숫자만 보면 단위가 바뀐 것(85 °C -> 185 °F)을
    「안 바뀜」 으로 읽는다."""


class RevisionChangedOut(BaseModel):
    name: str
    before_id: uuid.UUID
    after_id: uuid.UUID
    differences: list[RevisionDifferenceOut]


class RevisionCompareOut(BaseModel):
    """두 판의 차이 — **더해진 것 · 없어진 것 · 조건이 바뀐 것** 셋.

    개정이 오면 딸린 수십 건 중 **무엇을 다시 봐야 하는지**가 문제다. 「전부 다시」 는
    그날 일을 멈추고 「아무것도 안 봄」 은 바뀐 조건을 놓친다 — 그 사이를 이 답이 메운다.
    """

    document_id: uuid.UUID
    before: RevisionBriefOut
    after: RevisionBriefOut
    added: list[RevisionTestBriefOut]
    """뒤 판에만 있는 시험."""
    removed: list[RevisionTestBriefOut]
    """앞 판에만 있는 시험. **없어진 것이지 지워진 것이 아니다** — 앞 판의 줄은 남는다."""
    changed: list[RevisionChangedOut]
    unchanged_count: int
    """둘 다 있고 조건도 같은 것. **이 수가 크면 개정의 범위가 좁다는 뜻이다.**"""


class CapabilityPreviewRequest(Request):
    """아직 저장 안 한 조건으로 장비를 본다 — **적으면서 보는 자리.**"""

    test_item_term_ids: list[uuid.UUID] = Field(default_factory=list)
    attributes: list[AttributeValueIn] = Field(default_factory=list)


class SiblingTestOut(BaseModel):
    """이름이 같은 다른 시험 — 적용군·규격서·판이 무엇으로 갈렸나."""

    id: uuid.UUID
    name: str
    status: str
    product_group: str | None
    spec_document_code: str | None
    document_revision_label: str | None


class SkippedConditionOut(BaseModel):
    """물음에서 뺀 조건과 그 이유. **조용히 빼지 않는다** — 다 본 것처럼 읽힌다."""

    label: str
    reason: str


class CapabilityItemOut(BaseModel):
    """이 시험이 쓰는 시험 항목 하나에 대한 답."""

    term_id: uuid.UUID
    value: str
    total: int
    """조건을 걸고도 남은 장비 수. `hits` 는 그중 앞에서부터 상한까지다."""
    unmet_count: int
    """조건이 **안 되는** 것으로 판정돼 빠진 장비 수. 0 대라는 답이 「등록이 없어서」 인지
    「조건이 안 맞아서」 인지를 가른다."""
    hits: list[SearchHit]


class CapabilitySetOut(BaseModel):
    """조건 묶음 하나의 답 — 「주 조건으로는 12대, 불량 시 조건으로는 8대」."""

    set_label: str | None
    """묶음 이름. `null` 이면 이름 없는 한 벌이다."""
    conditions_asked: int
    skipped: list[SkippedConditionOut]
    items: list[CapabilityItemOut]


class CapabilityOut(BaseModel):
    """「이 시험, 어느 장비로 돌리나」 의 답 — 조건 속성을 그대로 검색 조건으로 옮긴 것."""

    test_id: uuid.UUID
    conditions_asked: int
    """검색에 넘긴 조건 물음 수. 범위 하나는 물음 둘이다(위로 얼마까지 · 아래로 얼마까지)."""
    skipped: list[SkippedConditionOut]
    items: list[CapabilityItemOut]
    """**모든 묶음을 한꺼번에** 만족하는 장비 — 예외 경로까지 이 시험을 통째로 돌릴 장비다."""
    sets: list[CapabilitySetOut] = []
    """묶음마다 따로 답한 것. **묶음이 둘 이상일 때만 찬다.**

    주 조건 80 °C 와 「불량 시」 70 °C 를 섞어 물으면 아무도 요구하지 않는 조건이 만들어지고,
    그 조건으로 장비가 걸러지는데 왜 걸러졌는지가 화면에 안 나온다. 비어 있으면 조건이 한
    벌이라는 뜻이고, 그때는 `items` 가 곧 그 한 벌의 답이다."""
