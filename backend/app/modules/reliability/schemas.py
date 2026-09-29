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
    action: Literal["confirm", "reject", "delete"]
    reason: str | None = Field(default=None, max_length=500)
    """`reject` 일 때만 쓴다(그때는 필수)."""


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
    test_item_term_ids: list[uuid.UUID] = Field(default_factory=list)
    attributes: list[AttributeValueIn] = Field(default_factory=list)
    """항목 값. `definition_id` 가 없고 `new_label` 이 있으면 초안 항목이 생긴다."""


class ReliabilityTestUpdateRequest(Request):
    """안 보낸 칸은 그대로. `test_item_term_ids` 는 보내면 **통째로** 바뀐다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    purpose: str | None = Field(default=None, max_length=4000)
    test_item_term_ids: list[uuid.UUID] | None = None
    attributes: list[AttributeValueIn] | None = None
    """보내면 통째로 바뀐다 — 시험 항목과 같은 규칙."""


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


class CapabilityOut(BaseModel):
    """「이 시험, 어느 장비로 돌리나」 의 답 — 조건 속성을 그대로 검색 조건으로 옮긴 것."""

    test_id: uuid.UUID
    conditions_asked: int
    """검색에 넘긴 조건 물음 수. 범위 하나는 물음 둘이다(위로 얼마까지 · 아래로 얼마까지)."""
    skipped: list[SkippedConditionOut]
    items: list[CapabilityItemOut]
