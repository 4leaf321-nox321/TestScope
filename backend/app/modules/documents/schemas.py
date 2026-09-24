"""사내 규격서 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SpecDocumentOut(BaseModel):
    id: uuid.UUID
    workspace_slug: str
    workspace_name: str
    code: str
    title: str
    revision: str | None
    note: str | None
    file_count: int
    """붙은 파일 수. **목록이 낱장을 받지 않는다** — 줄마다 받아 오면 스무 줄에 스무 번을
    왕복한다. 수만 보이고, 누르면 그때 받는다."""
    linked_test_count: int
    """이 규격서를 가리키는 신뢰성 시험 수. **0 이면 아무도 안 쓰는 문서다** — 지워도
    되는지 판단할 자리가 여기뿐이다."""
    can_edit: bool
    """요청한 사람이 고칠 수 있나 — 그 부서의 관리자 또는 시스템 관리자. 화면이 단추를
    보일지 정하는 데 쓴다. 판정은 서버가 한다."""
    created_at: datetime
    updated_at: datetime


class SpecDocumentCreateRequest(BaseModel):
    workspace_slug: str
    code: str = Field(min_length=1, max_length=100)
    """문서관리 시스템의 번호를 그대로 — MX-REL-012."""
    title: str = Field(min_length=1, max_length=300)
    revision: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=4000)


class SpecDocumentUpdateRequest(BaseModel):
    """안 보낸 칸은 그대로."""

    code: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    revision: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=4000)
    workspace_slug: str | None = None
