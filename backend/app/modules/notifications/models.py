"""알림 — **나에게 온 것.**

공지가 모두에게 가는 방송이라면 알림은 한 사람에게 가는 편지다. 가입 승인, 교정
만료 임박, 내가 담당인 장비의 상태 변경처럼 **받는 사람이 정해진** 일이 여기 온다.

메일이 없는 환경이라 이것이 유일한 전달 경로다. 그래서 읽음 상태를 서버가 든다 —
브라우저에만 두면 다른 PC 에서 다시 뜬다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50), index=True)
    """account.approved · calibration.due · equipment.status_changed."""
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    """눌렀을 때 갈 곳. **없으면 알림은 읽고 끝나는 글이 된다** — 사람은 그것을
    보고 나서 무엇을 해야 할지 스스로 찾아야 한다."""

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
