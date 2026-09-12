"""축에 속성 칸 정의를 둔다 — 편집 화면이 값의 attributes 를 칸으로 그릴 수 있게.

값의 `attributes` 는 자유 JSON 이라 화면이 무엇을 그릴지 몰랐다. 물성은 기호·단위·설명을
갖는데 그것을 편집할 자리가 없었고, JSON 을 통째로 보이면 아무도 안 고친다. 축이 자기
값의 칸을 말한다(`attribute_schema`). 행(물성 축의 칸)은 `reference.py` 가 심는다.

Revision ID: 0015_vocabulary_attribute_schema
Revises: 0014_test_item_properties
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_vocabulary_attribute_schema"
down_revision = "0014_test_item_properties"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vocabularies",
        sa.Column(
            "attribute_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("vocabularies", "attribute_schema")
