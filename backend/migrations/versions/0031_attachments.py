"""그림과 첨부 — **파일은 한 벌, 붙는 자리는 여럿.**

사내 시험 카드에는 그림이 들어간다. 그런데 **어느 칸에 붙는지가 문서마다 다르다** —
어떤 문서는 시험 절차에, 어떤 문서는 판정 기준에, 어떤 것은 아무 칸에도 안 붙는다. 칸마다
그림 칸을 만들면 대부분 빈 칸으로 서고, 새 자리가 생길 때마다 스키마가 바뀐다.

그래서 **붙는 자리를 데이터로 받는다**(`attachments.definition_id`, 비울 수 있다).

표를 둘로 가르는 이유는 **같은 그림이 여러 시험에 붙기 때문**이다(표준 치구 사진 · 합격
예시). 내용이 같으면(`sha256`) 파일은 하나만 두고 붙는 줄만 늘린다 — 안 그러면 같은 그림이
수십 벌 쌓이고, 백업이 그만큼 커진다.

Revision ID: 0031_attachments
Revises: 0030_attribute_pairs
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_attachments"
down_revision = "0030_attribute_pairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("id", sa.UUID(), primary_key=True),
        # **내용이 곧 이름이다.** 같은 그림을 두 번 올려도 파일은 하나다.
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # 모델이 `unique=True, index=True` 라 **유일 색인**이다 — UniqueConstraint 로 걸면
    # `alembic check` 가 매번 어긋남을 말한다(실측 2026-09-23).
    op.create_index("ix_stored_files_sha256", "stored_files", ["sha256"], unique=True)
    op.create_table(
        "attachments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("object_id", sa.UUID(), nullable=False),
        # 어느 칸에 붙나. **비울 수 있다** — 아무 칸에도 안 붙는 그림이 실제로 있다.
        # 칸이 지워지면 그림은 카드 전체로 내려온다(SET NULL) — 그림까지 사라지면 안 된다.
        sa.Column(
            "definition_id",
            sa.UUID(),
            sa.ForeignKey("attribute_definitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # 파일은 RESTRICT 다 — 붙어 있는 파일을 지우는 길은 참조가 0 이 된 뒤뿐이다.
        sa.Column(
            "file_id",
            sa.UUID(),
            sa.ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        # 설명은 비울 수 있지만 화면이 채우라고 조른다 — MCP 는 그림을 못 보고
        # 이 글자만 읽는다. 설명 없는 그림은 AI 에게 없는 것과 같다.
        sa.Column("caption", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
    )
    op.create_index("ix_attachments_object", "attachments", ["target", "object_id"])
    op.create_index("ix_attachments_file", "attachments", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_file", table_name="attachments")
    op.drop_index("ix_attachments_object", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_stored_files_sha256", table_name="stored_files")
    op.drop_table("stored_files")
