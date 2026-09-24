"""사내 규격서 — **공개 규격과 다른 표.**

`test_methods` 는 공개 규격이 사는 자리다(ASTM E8 · ISO 6892 · KS, 601건). 출처가 장비
카탈로그이고, 전사 공용이며, 시스템 관리자가 통제하고, 판이 제정 기관의 것이다.

사내 규격서는 전부 다르다 — **부서가 만들고 부서가 고치고**, 개정이 사내 결재를 따르고,
밖에서는 존재조차 모른다. 한 표에 섞으면 601건이 오염되고 「우리가 인용하는 공개 규격」 을
세는 모든 숫자가 틀어진다.

신뢰성 시험은 「규격서」 칸(`kind="document"`)으로 이 표를 **드롭다운으로** 가리킨다.
그 칸은 0034 에서 한 번 걷어냈던 것인데, 그때는 기준정보 값(`kind="term"`)이라 문서
자체를 담지 못했다 — 이번에는 파일이 붙는 줄을 가리킨다.

Revision ID: 0035_spec_documents
Revises: 0034_spec_document_to_file
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_spec_documents"
down_revision = "0034_spec_document_to_file"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spec_documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        # **비울 수 없다** — 전사 사내 규격서는 없다. 누구에게 물어야 하는지가 이 칸이다.
        sa.Column(
            "workspace_id",
            sa.UUID(),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        # 판은 **줄을 나누지 않는다.** 개정될 때마다 걸어 둔 시험 수십 건의 링크를 사람이
        # 옮기게 되면 아무도 안 옮긴다.
        sa.Column("revision", sa.String(length=30), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_spec_documents_workspace_id", "spec_documents", ["workspace_id"])
    op.create_index("ix_spec_documents_code", "spec_documents", ["code"])
    # 같은 부서에 같은 번호는 하나 — 지운 것은 뺀다.
    op.create_index(
        "uq_spec_documents_workspace_code",
        "spec_documents",
        ["workspace_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "attribute_values",
        sa.Column(
            "ref_document_id",
            sa.UUID(),
            # RESTRICT — 걸려 있는 규격서를 지우면 그 시험이 무엇을 따랐는지 알 수 없다.
            sa.ForeignKey("spec_documents.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("attribute_values", "ref_document_id")
    op.drop_index("uq_spec_documents_workspace_code", table_name="spec_documents")
    op.drop_index("ix_spec_documents_code", table_name="spec_documents")
    op.drop_index("ix_spec_documents_workspace_id", table_name="spec_documents")
    op.drop_table("spec_documents")
