"""사내 규격서 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.shared.schemas import Request


class SpecDocumentOut(BaseModel):
    id: uuid.UUID
    workspace_slug: str
    workspace_name: str
    code: str | None
    """문서 번호. **없을 수 있다** — 번호가 안 붙은 사내 문서가 실제로 있다."""
    title: str
    revision: str | None
    """지금 판. 이력은 `revisions` 가 줄로 갖는다."""
    pages: str | None = None
    """어디를 봤나 — 「12-18」."""
    is_excerpt: bool = False
    """발췌인가. **전문을 안 본 채 옮긴 것은 그렇게 보여야 한다.**"""
    source_path: str | None = None
    """원본이 어디 있나 — 사내 경로·URL. 첨부를 못 올리는 문서가 있다."""
    note: str | None
    revisions: list[SpecDocumentRevisionOut] = []
    """개정 이력 — 나중 판이 먼저. **목록에서는 비워 보낸다**(낱장을 받지 않는다)."""
    submitted_via: str | None = None
    """기계 자격으로 올렸으면 그 토큰 이름. **줄에 보인다** — 사람이 넣은 것과 구별이
    안 되면 검토하는 사람이 무엇을 더 봐야 하는지 모른다."""
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


class SpecDocumentRevisionOut(BaseModel):
    id: uuid.UUID
    label: str
    issued_on: date | None
    summary: str | None
    """무엇이 바뀌었나. **이 한 줄이 재검토의 범위를 정한다** — 「오타 수정」 이면 딸린
    시험을 다시 볼 이유가 없고, 「시험 온도 상향」 이면 전부 다시 봐야 한다."""
    sort_order: int
    submitted_via: str | None = None
    stale_test_count: int = 0
    """이 개정을 **아직 안 본** 시험 수. 개정이 올라와도 확정은 그대로 두므로, 이 수가
    「남은 일」 이다. 사람이 본 것부터 줄어든다."""
    created_at: datetime


class SpecDocumentRevisionRequest(Request):
    label: str = Field(min_length=1, max_length=60)
    """판 이름 — 「18」 · 「Rev.3」. 문서가 적은 그대로."""
    issued_on: date | None = None
    summary: str | None = Field(default=None, max_length=4000)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    """비우면 지금 있는 것 다음 자리. **날짜만으로는 못 가른다** — 날짜 없는 개정이 있다."""


class SpecDocumentCreateRequest(Request):
    workspace_slug: str
    code: str | None = Field(default=None, max_length=100)
    """문서관리 시스템의 번호를 그대로 — MX-REL-012.

    **비워도 된다.** 번호가 안 붙은 문서가 있는데 필수로 두었더니 옮기는 사람이 번호를
    지어냈다 — 지어낸 번호는 문서관리 시스템의 번호인 줄 알고 누가 찾으러 간다."""
    title: str = Field(min_length=1, max_length=300)
    revision: str | None = Field(default=None, max_length=30)
    pages: str | None = Field(default=None, max_length=60)
    """본 자리 — 「12-18」. 두꺼운 규격서에서 시험 하나가 나온 쪽이다."""
    is_excerpt: bool = False
    """발췌로 올리나. 전문을 안 봤으면 참으로 둔다."""
    source_path: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=4000)


class SpecDocumentUpdateRequest(Request):
    """안 보낸 칸은 그대로."""

    code: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    revision: str | None = Field(default=None, max_length=30)
    pages: str | None = Field(default=None, max_length=60)
    is_excerpt: bool | None = None
    source_path: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=4000)
    workspace_slug: str | None = None
