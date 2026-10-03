"""공지 API 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import Request


class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str
    level: str
    is_popup: bool
    published_at: datetime | None
    expires_at: datetime | None
    author_name: str | None
    read: bool
    """내가 읽었나. **서버가 든다** — 브라우저에만 두면 다른 PC 에서 또 뜬다."""
    created_at: datetime


class NoticeWriteRequest(Request):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    level: str = Field(default="info", pattern="^(info|warning|urgent)$")
    is_popup: bool = False
    publish: bool = True
    """false 면 초안으로 둔다. 급한 공지를 반쯤 쓰다 저장하는 일이 실제로 있다."""
    expires_at: datetime | None = None


class NoticeUpdateRequest(Request):
    """고치기 — **안 보낸 칸은 안 바꾼다**(`exclude_unset`). 게시는 따로 한다(`/publish`):
    고치다가 저장 단추 하나로 전사에 나가면 그 단추가 무섭다."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    level: str | None = Field(default=None, pattern="^(info|warning|urgent)$")
    is_popup: bool | None = None
    expires_at: datetime | None = None
