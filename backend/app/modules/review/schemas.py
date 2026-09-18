"""검토함의 응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueueOut(BaseModel):
    key: str
    label: str
    description: str
    multi: bool
    """여러 개를 고르는 물음인가."""
    open: int
    decided: int
    skipped: int
    gone: int
    voted: int
    """열린 것 중 의견이 하나라도 모인 줄 — 확정할 사람이 먼저 볼 것."""
    """대상이 없어져 닫힌 것 — 정한 것과 다르다."""


class FactOut(BaseModel):
    """대상을 이해하는 사실 한 줄. 「제조사: Instron」 「지금 하는 시험: 인장 · 압축」."""

    label: str
    value: str
    link: str | None = None


class CandidateOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    label: str
    recommended: bool = False
    reason: str | None = None
    """왜 추천하는가. **추천 옆에 늘 붙는다** — 근거 없는 추천은 첫 보기를 누르게 만들
    뿐이다."""
    sources: list[str] = []
    """근거의 출처 — 페이지 url 이나 논문 id. 「계열이 하는 규격」 처럼 밖에서 온 후보는
    사람이 링크를 열어 보고 판단한다."""


class VoteOut(BaseModel):
    """한 사람의 의견. 확정이 아니다 — 데이터를 안 건드린다."""

    user_id: uuid.UUID
    user: str
    choice: list[str]
    note: str | None
    at: datetime


class ProposalOut(BaseModel):
    id: uuid.UUID
    queue: str
    subject_key: str
    subject_id: uuid.UUID | None
    subject_label: str
    context: str | None
    question: str | None = None
    """무엇을 묻는지 — 완전한 문장. 화면이 대상 이름 아래에 그린다."""
    facts: list[FactOut] = []
    link: str | None
    """대상 상세로 가는 링크. 후보만으로 못 정할 때 원문을 보러 가는 길."""
    candidates: list[CandidateOut]
    payload: dict[str, Any]
    status: str
    """open · decided · skipped · gone(대상 없어짐)."""
    choice: list[str] | None
    followed: bool | None
    note: str | None
    decided_by: str | None
    decided_at: datetime | None
    votes: list[VoteOut]
    """모인 의견. 갈리는 줄이 보이게 — 확정하는 사람이 다수를 미리 본다."""
    my_vote: list[str] | None
    """보는 사람이 낸 의견. 없으면 None."""


class ProposalPage(BaseModel):
    items: list[ProposalOut]
    total: int


class DecideRequest(BaseModel):
    """고른 것. 후보에 없는 코드도 된다(「직접 고르기」) — 다만 그 큐의 어휘여야 한다."""

    choice: list[str] = Field(max_length=20)
    """빈 목록은 「해당 없음」 — 검색축이 없는 게 맞다 같은 결정."""
    note: str | None = Field(default=None, max_length=1000)


class VoteRequest(BaseModel):
    """의견 하나. 후보에 없는 코드도 된다(직접 고르기)."""

    choice: list[str] = Field(max_length=20)
    note: str | None = Field(default=None, max_length=1000)


class RefreshResult(BaseModel):
    open: dict[str, int]
