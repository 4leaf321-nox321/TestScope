"""작업 큐 — 브로커 없이 DB 한 표로.

ReportArchive(p47)·MatNexus 가 검증한 방식이다: `jobs` 표 + `SELECT … FOR UPDATE
SKIP LOCKED`. 폐쇄망 윈도우 서버에 Redis·RabbitMQ 를 반입하는 것은 반입물이 하나
더 느는 일이고, 우리 규모에서는 이득이 없다.

첫 사용처는 의미 검색 색인(임베딩)이다 — 저장 요청 안에서 임베딩 왕복(수백 ms)을
하지 않으려고. 그러나 임베딩 전용이 아니라 범용으로 둔다: 반입 뒤 후처리, 주기
점검처럼 「요청 밖에서 시간이 걸리는 일」 이 이미 몇 있다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: queued  → 대기
#: running → 워커가 집어감(locked_at·locked_by 로 누가 언제)
#: done    → 성공
#: failed  → 재시도 한도까지 실패. 사람이 봐야 한다
JOB_STATUSES = ("queued", "running", "done", "failed")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(50), index=True)
    """핸들러를 고르는 이름. `app/jobs/kinds.py` 의 상수, `handlers.py` 의 레지스트리 키."""

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    """재시도 백오프에 쓴다. 실패하면 뒤로 미뤄 다시 집어간다."""

    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """워커 식별자(호스트:PID). 워커가 죽었을 때 어느 작업이 물려 있었는지 알아야 한다."""

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    """실패 사유. 삼키면 「왜 실패했나」 를 물을 자리가 없다."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
