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
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SpecDocument(Base):
    """사내 규격서 한 건. 파일은 첨부(`target="spec_document"`)로 붙는다."""

    __tablename__ = "spec_documents"
    __table_args__ = (
        # 같은 부서에 같은 문서 번호는 하나 — 지운 것은 빼고(부분 유일 인덱스).
        # 같은 부서에 같은 문서 번호는 하나 — 지운 것과 **번호 없는 것**은 뺀다.
        # 번호가 안 붙은 사내 문서가 실제로 있고, 널끼리는 서로 다르다고 본다.
        Index(
            "uq_spec_documents_workspace_code",
            "workspace_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND code IS NOT NULL"),
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

    code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    """문서 번호 — MX-REL-012. 문서관리 시스템의 번호를 그대로 쓴다.

    **비울 수 있다.** 번호가 안 붙은 사내 문서가 실제로 있는데 필수로 두었더니, 옮기는
    사람이 번호를 지어내거나 등록을 포기했다 — 지어낸 번호는 문서관리 시스템의 번호인 줄
    알고 누가 찾으러 간다. 없으면 없다고 두고 제목으로 찾는다."""
    title: Mapped[str] = mapped_column(String(300))
    revision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """지금 판 — Rev.3 · 2024-05. 이력은 `spec_document_revisions` 가 줄로 갖는다."""
    pages: Mapped[str | None] = mapped_column(String(60), nullable=True)
    """어디를 봤나 — 「12-18」. 두꺼운 규격서에서 시험 하나가 나온 자리다."""
    is_excerpt: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    """발췌인가. **전문을 안 본 채 옮긴 것은 그렇게 보여야 한다** — 안 보이면 읽는 사람은
    이 문서를 다 반영한 줄 안다."""
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    """원본이 어디 있나 — 사내 경로·URL. 첨부를 못 올리는 문서(대외비·용량)가 있는데,
    그때 「어디 가면 있다」 가 비고 문장에 섞여 들어가 있었다."""
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_via: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """기계 자격으로 올렸으면 그 토큰 이름. 사람이 화면에서 넣었으면 비어 있다.

    **AI 가 규격서를 등록할 수 있게 열면서 붙인다**(2026-09-30). 출처를 기계가 못 붙이면
    시험은 들어오는데 근거 문서가 안 들어와, 값이 틀렸을 때 되짚을 자리가 없다. 열되
    **누가 넣었는지는 줄에 보여야** 한다 — 사람이 등록한 것과 구별이 안 되면 검토하는
    사람이 무엇을 더 봐야 하는지 모른다(신뢰성 시험의 `submitted_via` 와 같은 자리)."""

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


class SpecDocumentRevision(Base):
    """규격서의 개정 한 줄.

    **글자 하나로는 「이 시험은 개정 18에서 신설」 을 못 적는다.** 개정을 줄로 쌓아야 시험이
    어느 판에서 들어왔는지, 사람이 어느 판까지 확인했는지를 각각 가리킬 수 있다.

    개정이 올라와도 **딸린 시험은 확정인 채로 둔다** — 수십 건이 한꺼번에 후보로 내려가면
    그날 일이 멈추고, 멈춘 일은 미뤄진다. 대신 「개정 19 기준으로 아직 안 본 시험」 이라는
    표가 붙고, 사람이 본 것부터 그 표를 뗀다.
    """

    __tablename__ = "spec_document_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "label", name="uq_spec_document_revisions_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("spec_documents.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(60))
    """판 이름 — 「18」 · 「Rev.3」 · 「2024-05」. 문서가 적은 그대로 쓴다."""
    issued_on: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    """무엇이 바뀌었나. **이 한 줄이 재검토의 범위를 정한다** — 「오타 수정」 이면 딸린
    시험을 다시 볼 이유가 없고, 「시험 온도 상향」 이면 전부 다시 봐야 한다."""
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    """어느 것이 나중 판인가. **날짜만으로는 못 가른다** — 날짜가 없는 개정이 있다."""
    submitted_via: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
