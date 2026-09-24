"""토큰 — refresh 폐기 목록과 PAT.

**refresh 토큰을 JWT 로 만들지 않는다.** JWT 는 서버가 상태를 갖지 않으므로 발급한
뒤에는 되돌릴 수 없다. 그러면 탈취된 토큰이 만료까지 유효하고, 끊을 방법이 없다.
그래서 refresh 는 불투명 난수이고 여기 한 행으로 존재한다 — 행을 지우거나
revoked_at 을 채우면 즉시 무효다.

원문은 어디에도 저장하지 않는다. sha256 해시만 둔다. DB 가 새어도 남의 세션을
탈취할 수 없어야 한다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    """회전 이력. 폐기된 토큰이 다시 쓰이면 탈취 신호로 볼 수 있다 — 그 판정에
    "방금 회전한 것인가" 를 물으려면 사슬이 필요하다(services.rotate_refresh)."""

    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)


#: 토큰이 가질 수 있는 범위.
#:
#:   read            모든 읽기
#:   equipment:write 보유 장비·시험 항목·교정
#:   catalog:write   계열·기종·사양·온톨로지
#:
#: **왜 나누나.** 카탈로그 쓰기는 시스템 관리자 몫인데, MCP 용 토큰에 그 계정을
#: 주면 계정 관리와 서버 설정까지 함께 열린다. 자동화가 필요한 것은 그중 둘뿐이다.
#:
#: 사람 세션에는 이것을 안 건다 — **그 사람의 권한이 이미 한계**다. 범위는 기계
#: 자격에만 있는 개념이고, 둘을 같은 축으로 섞으면 화면에서 되던 일이 이유 없이
#: 막힌다.
PAT_SCOPES = ("read", "equipment:write", "catalog:write")


class PersonalAccessToken(Base):
    """장비 PC·스크립트가 API 를 부를 때 쓰는 자격 증명.

    장비 상태나 교정 이력을 자동으로 밀어 넣는 연계가 붙을 때 무슨 자격으로
    부를지가 지금 정해져 있어야 토큰 체계가 둘로 갈라지지 않는다. 사람 세션
    (refresh)과 기계 자격(PAT)은 수명과 폐기 방식이 다르므로 표를 나눈다.
    """

    __tablename__ = "personal_access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    """어디에 쓰는 토큰인지. 폐기할 때 이것만 보고 판단하게 된다."""

    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default='["read"]')
    """이 토큰으로 할 수 있는 일. **기본은 읽기뿐이다.**

    비어 있으면 아무것도 못 쓴다 — 목록에 없는 경로의 쓰기도 막힌다. 「모르는 것은
    막는다」 가 맞는 기본값이다: 새 엔드포인트가 생길 때마다 자동으로 열리면,
    그것을 알아채는 사람이 아무도 없다."""

    prefix: Mapped[str] = mapped_column(String(16), index=True)
    """평문의 앞자리. 목록 화면에서 어느 토큰인지 알아보게 하는 용도."""
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """마지막 사용 시각. 안 쓰는 토큰을 찾아 지우는 근거가 된다."""
