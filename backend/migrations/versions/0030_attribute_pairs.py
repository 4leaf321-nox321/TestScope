"""값 하나가 아니라 **짝의 목록**인 속성 — 등급별 수량 · 단계별 수량 · 적용 사양 매트릭스.

「A등급 4 · B등급 4」 처럼 **이름마다 숫자가 붙는** 칸이 사내 시험 카드에 여럿 있다. 지금
속성 값은 숫자·글자·날짜 같은 홑값 칸뿐이라 담을 자리가 없었다 — 글자로 뭉개 넣으면 사람은
읽어도 기계는 못 읽고, 그러면 그 칸을 만든 뜻이 없다.

`json_value` 한 칸을 더한다. 열을 종류마다 늘리지 않는 이유: 이런 칸은 모양이 **자라는**
쪽이고(짝 → 사양별 짝), 자랄 때마다 마이그레이션을 하면 운영이 그만큼 멈춘다.

Revision ID: 0030_attribute_pairs
Revises: 0029_attribute_targets
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030_attribute_pairs"
down_revision = "0029_attribute_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attribute_values",
        sa.Column("json_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attribute_values", "json_value")
