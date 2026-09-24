"""사내 규격서 — **부서가 만든 시험 문서 그 자체.**

## 왜 `test_methods` 가 아닌가

`test_methods` 는 **공개 규격**이 사는 표다(ASTM E8 · ISO 6892 · KS B 0802, 601건). 출처가
장비 카탈로그이고, 전사 공용이며, 시스템 관리자가 통제하고, 판이 제정 기관의 것이다.

사내 규격서는 전부 다르다 — **부서가 만들고 부서가 고치고**, 개정 주기가 사내 결재를 따르고,
밖에서는 존재조차 모른다. 한 표에 섞으면 601건이 오염되고 「우리가 인용하는 공개 규격」 을
세는 모든 숫자가 틀어진다.

## 판은 줄을 나누지 않는다

MX-REL-012 는 줄 하나고 `revision` 칸을 고친다. 개정본 PDF 는 첨부로 더한다.

판마다 새 줄을 만들면 **개정될 때마다 그 문서를 건 신뢰성 시험 수십 건의 링크를 사람이
옮겨야 한다.** 실무에서 문서가 개정되면 시험도 새 판을 따르는 것이 보통이므로, 링크가
안 끊기는 쪽이 맞다. 「그때는 Rev.2 로 했다」 는 시험 결과에 적을 일이지 이 표의 일이 아니다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SpecDocument(Base):
    """사내 규격서 한 건. 파일은 첨부(`target="spec_document"`)로 붙는다."""

    __tablename__ = "spec_documents"
    __table_args__ = (
        # 같은 부서에 같은 문서 번호는 하나 — 지운 것은 빼고(부분 유일 인덱스).
        Index(
            "uq_spec_documents_workspace_code",
            "workspace_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    """만든 부서. **비울 수 없다** — 전사 사내 규격서는 없다. 누구에게 물어야 하는지가
    이 칸이고, 고칠 수 있는 사람도 여기서 나온다."""

    code: Mapped[str] = mapped_column(String(100), index=True)
    """문서 번호 — MX-REL-012. 문서관리 시스템의 번호를 그대로 쓴다."""
    title: Mapped[str] = mapped_column(String(300))
    revision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """판 — Rev.3 · 2024-05. **줄을 나누지 않는다**(머리말 참고)."""
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """지우지 않는다. **그 문서로 한 시험의 결과가 밖에 나가 있다** — 번호가 무엇을
    가리켰는지는 남아야 한다."""
