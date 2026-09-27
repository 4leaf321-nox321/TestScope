"""첨부 API 의 응답 형태. **올리는 것은 multipart 라 요청 모델이 없다.**"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.schemas import Request


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


class AttachmentUpdateRequest(Request):
    """설명과 붙는 자리를 고친다. **파일은 안 바꾼다** — 다른 그림이면 새로 붙인다."""

    caption: str | None = Field(default=None, max_length=300)
    definition_id: uuid.UUID | None = None
    sort_order: int | None = None


class UploadTicketOut(BaseModel):
    """PC 의 파일을 서버로 바로 올릴 짧은 자격. **올리기 말고는 아무것도 못 한다.**"""

    ticket: str
    expires_in_seconds: int


class AttachExistingRequest(Request):
    """이미 올라온 파일을 다른 자리에도 가리킨다 — 바이트는 안 움직인다."""

    target: str
    object_id: uuid.UUID
    definition_id: uuid.UUID | None = None
    caption: str | None = Field(default=None, max_length=300)
    """안 주면 **원본의 설명을 그대로** 가져온다. 그림을 고른 이유가 대개 그 설명이다."""


class ExtractImagesResult(BaseModel):
    """문서에서 꺼낸 그림들. 건너뛴 것도 **세어서 말한다** — 조용히 빠지면 못 알아챈다."""

    source_attachment_id: uuid.UUID
    images: list[AttachmentOut]
    extracted: int
    skipped_oversize: int
    """장당 20 MB 를 넘어 안 꺼낸 것."""
    skipped_kind: int
    """emf·wmf 처럼 브라우저가 못 그리는 것."""
    skipped_duplicate: int
    """같은 그림이 여러 쪽에 나온 것(머리글 로고) — 한 번만 꺼낸다."""
