"""이름으로 찾기 — 요청과 응답."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ResolveRequest(BaseModel):
    """「이게 이미 있나?」

    AI 가 하는 첫 동작은 언제나 이것이다. 목록 검색(`?q=`)으로 흉내낼 수는 있지만,
    **흉내는 매번 조금씩 다르게 틀린다** — 「확실히 이것」 과 「후보 셋」 과 「없음」 을
    구별해 주지 않기 때문이다.
    """

    kind: str = Field(pattern="^(series|model|term|method)$")
    """무엇을 찾나. `term` 이면 `axis` 를 함께 준다."""
    text: str = Field(min_length=1, max_length=300)
    """사람이 쓰는 말 그대로. `Instron 68FM-300` · `인스트론 6800 시리즈` · `인장`."""
    axis: str | None = None
    """`kind=term` 일 때 어느 축인가 — manufacturer · equipment_category ·
    test_item · site · standard_body."""
    maker: str | None = None
    """제조사를 알면 준다. 같은 이름의 기종이 제조사마다 있을 때 후보가 줄어든다."""
    limit: int = Field(default=8, ge=1, le=25)


class ResolveCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    """사람이 읽는 이름. 제조사·계열까지 붙여 **후보끼리 구별되게** 만든다."""
    detail: str | None
    why: str
    """왜 후보인가 — `정확히 같음` · `별칭` · `이름에 포함`. **AI 가 이걸 보고
    고른다**: 근거 없이 첫 줄을 집으면 틀린 줄도 첫 줄이면 집는다."""


class ResolveResponse(BaseModel):
    """찾은 결과.

    `match` 가 세 값인 것이 요점이다.

        exact       하나로 정해졌다. `id` 를 그대로 쓰면 된다
        candidates  여럿이다. **고르지 말고 사람에게 물어라**
        none        없다. 만들거나, 비워 두거나 — 지어내지는 마라
    """

    match: str
    id: uuid.UUID | None
    label: str | None
    candidates: list[ResolveCandidate]
    hint: str
    """다음에 무엇을 하라는 한 줄. 오류가 아니라 **안내**다 — 이 응답은 언제나
    200 이고, 못 찾은 것은 실패가 아니다."""
