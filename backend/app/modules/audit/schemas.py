"""감사·접근 로그 응답 형태. **읽기만 있다** — 고칠 수 있으면 감사가 아니다."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    actor_label: str
    actor_client: str | None
    """어느 통로로 들어왔나 — 비어 있으면 화면, `mcp` 면 AI 도구.

    **이 칸이 없으면 화면이 「관리자가 바꿨습니다」 라고만 말한다.** 그 관리자가
    직접 눌렀는지 자기 토큰을 쥔 AI 가 눌렀는지는 다른 이야기다."""
    actor_token: str | None
    """쓴 개인 토큰의 이름."""
    target_table: str
    target_id: uuid.UUID | None
    target_label: str
    changes: dict[str, Any]
    reason: str | None
    request_id: str | None
    created_at: datetime


class AccessLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_label: str | None
    action: str
    path: str
    method: str
    status_code: int
    request_id: str | None
    client_ip: str | None
    created_at: datetime
