"""값에 순서 칸 — **회사가 정한 차례가 있는 축이 있다.**

사업부는 MX · VD · DA · NW · 의료기기 · GTR · SR · CS 순이다. 이름순이 아니고, 이름순으로
두면 CS 가 맨 앞에 서서 보는 사람이 「왜 CS 가 먼저지」 를 생각한다.

기본은 0 이라 **다른 축은 그대로 이름순**이다 — 순서를 안 정한 축에서 0 끼리 묶이고 그
안에서 이름으로 갈린다.

Revision ID: 0038_term_sort_order
Revises: 0037_division
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038_term_sort_order"
down_revision = "0037_division"
branch_labels = None
depends_on = None

#: 사업부의 차례. `reference.py` 의 DEFAULT_TERMS 와 같은 순서다.
DIVISION_ORDER = ["mx", "vd", "da", "nw", "medical", "gtr", "sr", "cs"]


def upgrade() -> None:
    op.add_column(
        "vocabulary_terms",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    for index, code in enumerate(DIVISION_ORDER, start=1):
        op.execute(
            sa.text(
                """
                UPDATE vocabulary_terms SET sort_order = :order
                 WHERE code = :code
                   AND vocabulary_id = (SELECT id FROM vocabularies WHERE slug = 'division')
                """
            ).bindparams(order=index * 10, code=code)
        )


def downgrade() -> None:
    op.drop_column("vocabulary_terms", "sort_order")
