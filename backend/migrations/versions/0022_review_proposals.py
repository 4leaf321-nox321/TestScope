"""검토함 — `review_proposals`.

반입이 못 정한 것(어느 시험의 규격인가 · 이 시험은 무슨 조건을 묻나 · 이 물성이 이 시험에서
나오나 · 이 사양을 정의로 올리나)을 후보·추천·근거와 함께 한 줄로 세워 두고, 도메인 전문가가
고르면 기존 API 가 움직인다. 누가 골랐고 추천을 따랐는지가 남는다.

Revision ID: 0022_review_proposals
Revises: 0021_notification_dedupe
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_review_proposals"
down_revision = "0021_notification_dedupe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue", sa.String(40), nullable=False),
        sa.Column("subject_key", sa.String(200), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_label", sa.String(300), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("candidates", postgresql.JSONB(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("choice", postgresql.JSONB(), nullable=True),
        sa.Column("followed", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "decided_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_by_label", sa.String(200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("queue", "subject_key", name="uq_review_proposals_subject"),
    )
    op.create_index("ix_review_proposals_queue", "review_proposals", ["queue"])
    op.create_index("ix_review_proposals_status", "review_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_review_proposals_status", table_name="review_proposals")
    op.drop_index("ix_review_proposals_queue", table_name="review_proposals")
    op.drop_table("review_proposals")
