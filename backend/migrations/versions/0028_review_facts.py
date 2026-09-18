"""검토함 줄에 물음(`question`)과 근거 자료(`facts`) — 이름만 주고 묻지 않는다.

「3400」 만 보여 주고 「무슨 시험을 하나」 를 물으면 도메인 전문가도 못 정한다. 줄마다 완전한
문장의 물음과, 대상을 이해하는 사실 몇 줄(제조사·분류·소개·지금 하는 시험·인용 규격 …)을
붙인다. 값은 `review.refresh` 가 채운다 — 배포 뒤 「후보 다시 세우기」 한 번.

Revision ID: 0028_review_facts
Revises: 0027_attributes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028_review_facts"
down_revision = "0027_attributes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_proposals", sa.Column("question", sa.Text(), nullable=True))
    op.add_column(
        "review_proposals",
        sa.Column(
            "facts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("review_proposals", "facts")
    op.drop_column("review_proposals", "question")
