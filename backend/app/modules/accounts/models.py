"""계정.

소유권 승계를 위해 사용자는 **지우지 않고 정지**하는 것을 기본으로 둔다.
deleted_at 이 있는 행은 로그인할 수 없지만, 그 사람이 등록한 장비·역량 데이터의
소유자 참조는 살아 있다.

계정 상태를 불리언이 아니라 status 로 두는 이유: 셀프 가입 + 관리자 승인
방식에서는 "승인 대기" 가 활성/비활성과 별개의 상태다. is_active 하나로 두면
승인 대기와 정지를 구분할 수 없어, 관리자 화면이 "왜 로그인이 안 되는지" 를
설명하지 못한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: 계정 상태.
#:   pending    가입 신청. 로그인 불가. 관리자 승인 대기
#:   active     정상
#:   suspended  관리자가 정지. 자료는 남기고 접근만 막는다
USER_STATUSES = ("pending", "active", "suspended")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    """로그인 아이디. **이메일 형식을 강제하지 않는다** — 사내 관리자 계정은
    admin 처럼 짧은 아이디를 쓰고, 폐쇄망은 .local 같은 도메인을 쓴다."""
    password_hash: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(100))

    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    is_system_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    home_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    """대표 소속. 로그인해서 처음 서는 부서다. 비어 있으면 소속 중 첫 부서로
    떨어지는데 그것은 사람이 정한 값이 아니다 — 승인할 때 함께 정한다."""

    requested_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    """가입 신청 시 고른 희망 부서. 승인하면 멤버십이 생기고 이 값은 기록으로 남는다."""

    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    """거절 사유. SMTP 가 없어 통보가 앱 안에서만 되므로 반드시 남긴다."""

    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    """관리자가 만든 계정의 임시 비밀번호. 첫 로그인 때 변경을 강제한다 —
    시드 비밀번호가 그대로 남는 것이 가장 흔한 사고다."""

    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_failed_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """연속 실패를 세어 응답을 늦춘다. **잠그지는 않는다**(config.login_delay_after)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    """소프트 삭제. 행은 남고 접근만 끊긴다 — 자료의 소유자 참조를 잃지 않기 위해서다."""

    @property
    def can_sign_in(self) -> bool:
        return self.deleted_at is None and self.status == "active"
