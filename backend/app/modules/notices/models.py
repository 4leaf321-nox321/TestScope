"""공지 — **배포 없이 안내를 전한다.**

사내 설치에는 메일 서버가 없는 경우가 많다. 그러면 "다음 주에 서버를 내립니다"
같은 말을 전할 길이 앱 안에밖에 없다. 코드에 박아 배포하는 방식은 그 말을
고치는 데 배포가 필요해지므로, 결국 아무도 안 고친다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 공지의 급.
#:   info    보통
#:   warning 주의 — 화면 위에 색이 붙는다
#:   urgent  긴급 — 팝업으로 뜨고, 읽어야 닫힌다
NOTICE_LEVELS = ("info", "warning", "urgent")


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(20), default="info", server_default="info")

    is_popup: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    """읽지 않았으면 스스로 뜬다. **공지 화면에 들어가야만 보이면** 배포 없이
    안내를 전한다는 목적이 성립하지 않는다."""

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    """비어 있으면 초안이다. 초안을 상태 칸 대신 시각으로 두는 이유: 언제 게시했는지가
    그 자체로 답해야 하는 물음이다."""
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """지나면 목록에서 내려간다. **지우지 않는다** — 그때 무엇을 안내했는지는 남는다."""

    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NoticeRead(Base):
    """누가 읽었나. 팝업을 다시 안 띄우기 위한 것이자, 전달됐는지 아는 유일한 근거다."""

    __tablename__ = "notice_reads"
    __table_args__ = (UniqueConstraint("notice_id", "user_id", name="uq_notice_reads_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    notice_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
