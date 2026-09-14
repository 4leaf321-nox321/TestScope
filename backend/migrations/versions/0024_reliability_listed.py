"""부서에 「신뢰성 시험 메뉴에 올림」 표시 — `workspaces.reliability_listed`.

사이드바 「신뢰성 시험」 아래에 어느 부서를 세우나. 조직도를 통째로 펼치면 시험을
하는 부서 넷을 찾으려고 서른을 훑게 되므로, 관리자가 「부서 정보」 에서 고른다.

Revision ID: 0024_reliability_listed
Revises: 0023_review_votes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_reliability_listed"
down_revision = "0023_review_votes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "reliability_listed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "reliability_listed")
