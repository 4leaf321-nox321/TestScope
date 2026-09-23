"""첨부 API 의 응답 형태. **올리는 것은 multipart 라 요청 모델이 없다.**"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AttachmentOut(BaseModel):
    id: uuid.UUID
    target: str
    object_id: uuid.UUID

    definition_id: uuid.UUID | None
    """어느 칸에 붙었나. **비어 있으면 카드 전체**다 — 아무 칸에도 안 붙는 그림이 있다."""
    definition_label: str | None
    """그 칸의 이름. 화면이 정의 목록을 다시 안 받아도 되게 서버가 붙인다."""

    original_name: str
    caption: str
    """무엇을 찍은 그림인가. **MCP 는 그림을 못 본다** — AI 가 읽는 것은 이 글자뿐이다."""
    content_type: str
    bytes: int
    sort_order: int
    url: str
    """내려받는 자리. 화면이 `<img src>` 에 그대로 쓴다."""
    created_at: datetime


class AttachmentUpdateRequest(BaseModel):
    """설명과 붙는 자리를 고친다. **파일은 안 바꾼다** — 다른 그림이면 새로 붙인다."""

    caption: str | None = Field(default=None, max_length=300)
    definition_id: uuid.UUID | None = None
    sort_order: int | None = None
