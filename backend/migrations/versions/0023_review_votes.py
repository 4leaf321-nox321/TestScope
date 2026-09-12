"""검토함의 의견 — `review_votes`.

「의견 모으기」 와 「확정」 을 가른다. 로그인한 누구나 한 줄에 의견 하나를 내고(데이터는
안 건드림), 시스템 관리자가 모인 의견을 보고 확정한다. 갈리는 줄이 눈에 보이게.

Revision ID: 0023_review_votes
Revises: 0022_review_proposals
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_review_votes"
down_revision = "0022_review_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_label", sa.String(200), nullable=False),
        sa.Column("choice", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("proposal_id", "user_id", name="uq_review_votes_user"),
    )
    op.create_index("ix_review_votes_proposal_id", "review_votes", ["proposal_id"])
    op.create_index("ix_review_votes_user_id", "review_votes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_review_votes_user_id", table_name="review_votes")
    op.drop_index("ix_review_votes_proposal_id", table_name="review_votes")
    op.drop_table("review_votes")
