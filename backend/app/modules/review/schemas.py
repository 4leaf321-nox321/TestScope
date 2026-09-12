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


class CandidateOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    label: str
    recommended: bool = False
    reason: str | None = None
    """왜 추천하는가. **추천 옆에 늘 붙는다** — 근거 없는 추천은 첫 보기를 누르게 만들
    뿐이다."""


class ProposalOut(BaseModel):
    id: uuid.UUID
    queue: str
    subject_key: str
    subject_id: uuid.UUID | None
    subject_label: str
    context: str | None
    link: str | None
    """대상 상세로 가는 링크. 후보만으로 못 정할 때 원문을 보러 가는 길."""
    candidates: list[CandidateOut]
    payload: dict[str, Any]
    status: str
    choice: list[str] | None
    followed: bool | None
    note: str | None
    decided_by: str | None
    decided_at: datetime | None


class ProposalPage(BaseModel):
    items: list[ProposalOut]
    total: int


class DecideRequest(BaseModel):
    """고른 것. 후보에 없는 코드도 된다(「직접 고르기」) — 다만 그 큐의 어휘여야 한다."""

    choice: list[str] = Field(max_length=20)
    """빈 목록은 「해당 없음」 — 검색축이 없는 게 맞다 같은 결정."""
    note: str | None = Field(default=None, max_length=1000)


class RefreshResult(BaseModel):
    open: dict[str, int]
