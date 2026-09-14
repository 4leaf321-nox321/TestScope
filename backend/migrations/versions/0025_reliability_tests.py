"""신뢰성 시험 — `reliability_tests` · `reliability_test_items`.

부서가 제품 개발·검증을 위해 수행하는 시험. 「시험 항목」(장비가 할 수 있는 측정, 전사
공용)과 다른 층이고, 시험 항목 하나 이상을 써서 돈다 — 그 링크가 두 번째 표다.
칸은 조사 중이라 이름·목적·시험 항목만 둔다.

Revision ID: 0025_reliability_tests
Revises: 0024_reliability_listed
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_reliability_tests"
down_revision = "0024_reliability_listed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reliability_tests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_reliability_tests_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_reliability_tests_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reliability_tests")),
    )
    op.create_index(
        op.f("ix_reliability_tests_workspace_id"),
        "reliability_tests",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "uq_reliability_tests_workspace_name",
        "reliability_tests",
        ["workspace_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "reliability_test_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reliability_test_id", sa.UUID(), nullable=False),
        sa.Column("test_item_term_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["reliability_test_id"],
            ["reliability_tests.id"],
            name=op.f("fk_reliability_test_items_reliability_test_id_reliability_tests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_item_term_id"],
            ["vocabulary_terms.id"],
            name=op.f("fk_reliability_test_items_test_item_term_id_vocabulary_terms"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reliability_test_items")),
        sa.UniqueConstraint(
            "reliability_test_id", "test_item_term_id", name="uq_reliability_test_items_pair"
        ),
    )
    op.create_index(
        op.f("ix_reliability_test_items_reliability_test_id"),
        "reliability_test_items",
        ["reliability_test_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reliability_test_items_test_item_term_id"),
        "reliability_test_items",
        ["test_item_term_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reliability_test_items_test_item_term_id"),
        table_name="reliability_test_items",
    )
    op.drop_index(
        op.f("ix_reliability_test_items_reliability_test_id"),
        table_name="reliability_test_items",
    )
    op.drop_table("reliability_test_items")
    op.drop_index(
        "uq_reliability_tests_workspace_name",
        table_name="reliability_tests",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(op.f("ix_reliability_tests_workspace_id"), table_name="reliability_tests")
    op.drop_table("reliability_tests")
