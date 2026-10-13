"""검토함의 응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import Request


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
    warning: str | None = None
    """고르기 전에 볼 것 — 「분류와 맞지 않음」 처럼. 경고가 있는 후보는 추천하지 않는다."""


class VoteOut(BaseModel):
    """한 사람의 의견. 확정이 아니다 — 데이터를 안 건드린다."""

    user_id: uuid.UUID
    user: str
    choice: list[str]
    note: str | None
    at: datetime
    mcp: bool = False
    """MCP(기계 자격)로 낸 의견인가 — 이름에도 「(MCP)」 가 붙는다."""


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
    skip_reason: str | None = None
    """보류 사유 키(evidence · expert · source · no_answer · other). 메모는 `note`."""
    skip_reason_label: str | None = None
    skipped_by: str | None = None
    skipped_at: datetime | None = None
    votes: list[VoteOut]
    """모인 의견. 갈리는 줄이 보이게 — 확정하는 사람이 다수를 미리 본다."""
    my_vote: list[str] | None
    """보는 사람이 낸 의견. 없으면 None."""


class ProposalPage(BaseModel):
    items: list[ProposalOut]
    total: int


#: 한 줄에서 고르는 수의 상한. 20 으로 두었더니 인용 규격이 스무 개 넘는 계열을 다 반영할 수
#: 없었다(후보는 한 줄 30 개까지 — 2026-10-13). 후보 수보다 넉넉히 둔다.
CHOICE_LIMIT = 200


class SkipRequest(Request):
    """보류 — 사유와 메모. 둘 다 비워도 되지만 비우면 나중에 왜 보류했는지 모른다."""

    reason: str | None = Field(
        default=None, pattern="^(evidence|expert|source|no_answer|other)$"
    )
    note: str | None = Field(default=None, max_length=1000)


class DecideRequest(Request):
    """고른 것. 후보에 없는 코드도 된다(「직접 고르기」) — 다만 그 큐의 어휘여야 한다."""

    choice: list[str] = Field(max_length=CHOICE_LIMIT)
    """빈 목록은 「해당 없음」 — 검색축이 없는 게 맞다 같은 결정."""
    note: str | None = Field(default=None, max_length=1000)
    add_to_citing: bool = False
    """규격의 시험 항목 물음 전용 — 고른 시험 항목이 없어 안 이어지는 인용 계열에 그 시험
    항목을 더해 잇는다. 안 주면 그 계열은 미정으로 남는다(응답 `payload.unlinked_series`)."""


class ChoicePreviewOut(BaseModel):
    """확정 전 미리보기 — 규격의 시험 항목 물음."""

    linked: list[str]
    """이 선택으로 이어지는 인용 계열."""
    unlinked: list[str]
    """그 시험 항목이 없어 **안 이어지는** 인용 계열."""
    off_candidates: list[str]
    """고른 것 중 후보 밖 시험 항목."""
    cut: list[str] = []
    """다시 정할 때 — 빠지는 항목으로만 이어져 있어 **끊기는** 계열."""
    movable: list[str] = []
    """사양 정의 승격 — 정의 값으로 옮겨질 줄(「기종: 값」)."""
    unmovable: list[str] = []
    """사양 정의 승격 — 정의의 종류로 못 읽어 **기종 고유 사양에 남을** 줄(「기종: 값」)."""
    kind: str | None = None
    """사양 정의 승격 — 세울 정의의 종류(number · range · text · boolean)."""


#: 한 번에 확정하는 줄 수의 상한. 한 쪽이 50 줄이라 넉넉하다 — 다른 일괄 처리와 같은 값.
BULK_LIMIT = 500


class DecideRecommendedRequest(Request):
    """고른 줄들을 **각자의 추천대로** 확정한다.

    추천이 없거나, **추천과 다른 의견이 있는** 줄은 확정하지 않고 이유와 함께 돌려준다 —
    한꺼번에 넘기는 것은 합의된 줄이고, 갈린 줄은 사람이 보고 하나씩 정한다.
    """

    ids: list[uuid.UUID] = Field(min_length=1, max_length=BULK_LIMIT)
    note: str | None = Field(default=None, max_length=1000)
    """감사에 남는 말. 비우면 「추천대로 한꺼번에 확정」 이 남는다 — 하나씩 정한 것과
    갈린다."""


class BulkDecideFailure(BaseModel):
    id: uuid.UUID
    code: str
    message: str


class BulkDecideResult(BaseModel):
    """줄마다 결과. **전부 되거나 전부 안 되거나로 두지 않는다** — 오십 줄 중 하나가 추천이
    없다는 이유로 마흔아홉 줄이 함께 막히면 안 된다."""

    requested: int
    done: list[uuid.UUID]
    failed: list[BulkDecideFailure]


class VoteRequest(Request):
    """의견 하나. 후보에 없는 코드도 된다(직접 고르기)."""

    choice: list[str] = Field(max_length=CHOICE_LIMIT)
    note: str | None = Field(default=None, max_length=1000)


class RefreshResult(BaseModel):
    open: dict[str, int]
