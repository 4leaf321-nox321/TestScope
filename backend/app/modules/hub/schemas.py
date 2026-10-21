"""허브 수신 — 화면 · API 가 주고받는 모양."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.shared.schemas import Request


class HubTypeOut(BaseModel):
    """카탈로그의 공개 타입 하나 — 받을지 고르는 자리."""

    slug: str
    label: str
    description: str = ""
    count: int
    """허브가 말한 객체 수(전량 수신 건수와 견준다)."""
    properties: int
    relations: list[str]
    selected: bool


class HubConnectionOut(BaseModel):
    base_url: str
    has_token: bool
    token_readable: bool
    """토큰을 풀 수 있나. 못 풀면 DB 를 옮겼거나 JWT_SECRET 이 바뀐 것 — 다시 입력."""
    token_set_at: datetime | None
    ca_bundle: str | None
    selected_types: list[str] | None
    """NULL 이면 공개 타입 전부(새 타입도 저절로)."""
    nightly_at: str
    enabled: bool
    catalog_revision: str | None
    catalog_as_of: str | None
    catalog_changed_at: datetime | None
    """구조가 실제로 바뀐 때 — 확인하면 비운다."""
    types: list[HubTypeOut]


class HubConnectionRequest(Request):
    """연계 설정. **토큰은 쓰기만 한다** — 비우면 그대로, `clear_token` 이면 지운다."""

    base_url: str = Field(default="", max_length=500)
    token: str | None = Field(default=None, max_length=4000)
    clear_token: bool = False
    ca_bundle: str | None = Field(default=None, max_length=500)
    selected_types: list[str] | None = None
    nightly_at: str = Field(default="01:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    enabled: bool = False


class HubCheckOut(BaseModel):
    """연결 점검 — 카탈로그를 받아 본 결과."""

    ok: bool
    message: str
    system: str | None = None
    revision: str | None = None
    as_of: str | None = None
    types: list[HubTypeOut] = []
    request_id: str | None = None


class HubStateOut(BaseModel):
    as_of: str | None
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    last_full_at: datetime | None
    stopped: bool


class HubTypeStatusOut(BaseModel):
    slug: str
    label: str
    axis_slug: str | None
    selected: bool
    catalog_count: int
    received: int
    """받아 둔 객체 수(비활성 포함)."""
    active: int
    """그중 사용 중인 것 — 전량 수신 뒤 카탈로그 수와 같아야 한다."""
    relations: int
    rows: HubStateOut | None
    relation_state: HubStateOut | None


class HubRunOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    full: bool
    status: str
    triggered_by: str | None
    counts: dict[str, Any]
    errors: list[dict[str, Any]]
    request_ids: list[str]
    duration_ms: int | None


class HubStatusOut(BaseModel):
    configured: bool
    enabled: bool
    nightly_at: str
    catalog_changed_at: datetime | None
    pending_job: str | None
    """대기 · 실행 중인 수신 작업(`queued` · `running`). 워커가 꺼져 있으면 대기에 머문다."""
    last_run: HubRunOut | None
    types: list[HubTypeStatusOut]


class HubRunRequest(Request):
    full: bool = False
    """전량 수신 — 기준 시각을 무시하고 다 받은 뒤 부재 대조까지."""


class HubRunQueued(BaseModel):
    job_id: uuid.UUID
    full: bool


class HubItemOut(BaseModel):
    """받은 객체 하나 — 누구나 본다(수신 데이터 조회)."""

    key: str
    label: str
    status: str
    state: str
    """사용 · 사용 중지 · 삭제 · 숨김 · 병합 · 부재."""
    merged_into: str | None
    previous_keys: list[str]
    properties: dict[str, Any]
    references: dict[str, str]
    """참조 속성 값의 이름(옛 식별자도 풀어서)."""
    hub_updated_at: str | None
    received_at: datetime
    term_id: uuid.UUID | None


class HubRelationOut(BaseModel):
    src: str
    relation: str
    dst: str
    dst_type: str
    dst_label: str | None
    deleted: bool


class HubItemDetailOut(HubItemOut):
    outgoing: list[HubRelationOut]
    incoming: list[HubRelationOut]


class HubItemPage(BaseModel):
    items: list[HubItemOut]
    total: int


class HubPublicTypeOut(BaseModel):
    """받아 둔 타입 하나 — 누구나 본다."""

    slug: str
    label: str
    axis_slug: str | None
    active: int
    total: int
    last_received_at: datetime | None
