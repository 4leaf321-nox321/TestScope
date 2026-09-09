"""접근 로그와 감사 로그 — **목적이 다르다.**

  접근 로그(AccessLog)  사용자 지원용. 누가 언제 어느 API 를 썼는가
  감사 로그(AuditEntry) 무결성용. 무엇이 바뀌었는가, 누가 승인했는가

둘을 한 표에 섞으면 보존 기간이 충돌한다 — 접근 로그는 몇 달이면 지워도 되지만
감사 로그는 남아야 한다. 처음부터 나눈다.

파일 로그(app.log)와도 역할이 다르다. 파일은 요청 단위 진단용이고 로테이션으로
사라지지만, 이것은 질의할 수 있어야 한다("지난주에 이 사람이 뭘 했나").
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccessLog(Base):
    __tablename__ = "access_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """로그인 전 요청도 남으므로 nullable. 계정이 지워져도 기록은 남는다."""

    action: Mapped[str] = mapped_column(String(30), index=True)
    """LOGIN / LOGOUT / API. 화면 방문은 SPA 라 서버가 모르므로 API 호출로 갈음한다."""

    path: Mapped[str] = mapped_column(String(300))
    method: Mapped[str] = mapped_column(String(10))
    status_code: Mapped[int] = mapped_column(Integer)

    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    """파일 로그와 잇는 끈. 이 값으로 app.log 에서 그 요청의 모든 줄을 찾는다."""

    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AuditEntry(Base):
    """감사 로그 — **무엇이 바뀌었고 누가 승인했는가.**

    ## 모든 변경을 담지 않는다

    담으면 아무도 안 읽는다. **되돌릴 수 없거나 권한이 실린 것**만 남긴다 —
    장비 폐기, 계정 상태, 기준정보 이름 변경처럼 "누가 그랬지" 가 실제로 문제가
    되는 일이다. 값 하나 고친 것까지 남기면 그 안에서 이걸 못 찾는다.

    ## 지워져도 남는다

    actor_id 는 SET NULL 이고 **이름을 함께 박아 둔다.** 계정이 지워지면 누가 했는지
    모르게 되는데, 그건 감사 로그가 존재하는 이유와 정면으로 어긋난다.

    ## 고치지 않는다

    이 표에는 updated_at 이 없다. 감사 기록을 고칠 수 있으면 감사가 아니다 —
    쓰는 길만 있고 고치는 길은 API 에도 없다.
    """

    __tablename__ = "audit_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    action: Mapped[str] = mapped_column(String(60), index=True)
    """equipment.retired 처럼 대상.한일. **과거형으로 적는다** — 일어난 일의
    기록이지 명령이 아니다."""

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_label: Mapped[str] = mapped_column(String(200))
    actor_client: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    """어느 통로로 들어왔나 — 화면인가, MCP 인가, 스크립트인가.

    `created_by_id` 는 토큰 소유자, 즉 **사람**이다. 그래서 그것만으로는 사람이
    넣은 것과 AI 가 넣은 것이 구별되지 않는다 — 반년 뒤 「이 300 kN 누가 넣었나」 에
    "관리자" 라고만 답하면 쓸모가 없다."""
    actor_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """쓴 개인 토큰의 이름. 「MCP-카탈로그봇」 이 만든 것을 셀 수 있고, 잘못
    들어왔을 때 **그 토큰 것만** 골라낼 수 있다."""
    """그때의 사람 이름. **계정이 지워져도 남아야 한다.**"""

    target_table: Mapped[str] = mapped_column(String(60), index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )
    """**외래키를 안 건다.** 지워진 대상의 기록이 그 삭제 때문에 사라지면 안 된다."""
    target_label: Mapped[str] = mapped_column(String(300))

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )
    """어느 부서의 일인가. 가시성 판정에 쓴다 — 여기도 FK 를 안 건다."""

    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    """{키: {before, after}}. **바뀐 것만** 담는다 — 통째로 스냅샷하면 표가 커지고
    무엇이 바뀌었는지는 오히려 안 보인다."""

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    """사람이 적은 사유. 없을 수 있다 — **없다고 안 남기지는 않는다.**"""

    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
