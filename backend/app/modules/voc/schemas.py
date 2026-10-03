"""VOC 의 들고 나는 모양."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.schemas import Request


class VocCreateRequest(Request):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    page_path: str | None = Field(default=None, max_length=300)
    """접수 당시 보던 화면. 화면이 알아서 채운다 — 사람에게 묻지 않는다."""


class VocMoveRequest(Request):
    """상태를 옮기거나(`to_status`), 말만 보태거나(지금 상태를 그대로 보낸다)."""

    to_status: str = Field(min_length=1, max_length=20)
    note: str | None = None


class VocEventOut(BaseModel):
    id: uuid.UUID
    at: datetime
    by_name: str | None
    from_status: str | None
    """비어 있으면 **등록**이다."""
    to_status: str
    note: str | None


class VocItemOut(BaseModel):
    id: uuid.UUID
    seq: int
    title: str
    status: str
    status_label: str
    """화면이 코드를 한국어로 다시 매기지 않게 **서버가 준다** — 두 벌로 두면 갈라진다."""
    created_by_name: str | None
    created_at: datetime
    status_at: datetime
    comment_count: int
    """이 건에 붙은 말의 수. 목록에서 「말이 오간 건」 을 눈으로 고른다."""


class VocDetailOut(VocItemOut):
    body: str
    page_path: str | None
    events: list[VocEventOut]
    can_move: list[str]
    """**내가** 지금 옮길 수 있는 상태. 화면이 권한을 다시 계산하면 서버와 갈라지고,
    그때 사람은 눌리는 단추가 400 을 돌려주는 것을 본다."""
    note_required: list[str]
    """그중 **말이 있어야** 옮겨지는 것. 안 알려 주면 400 을 받고 나서야 안다."""
    can_attach: bool = False
    """**내가** 자료(화면 갈무리 · 로그)를 붙이고 지울 수 있나 — 낸 사람과 시스템 관리자.
    화면이 따로 계산하면 서버와 갈라진다(`can_move` 와 같은 이유)."""
