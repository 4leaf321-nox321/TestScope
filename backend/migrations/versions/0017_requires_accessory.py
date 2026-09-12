"""옵션 부속이 있어야 나오는 값에 표시를 둔다 — 사양값·계열 조건·장비 조건.

카탈로그가 「-180~320 °C」 를 항온조 옵션 기준으로 적는 일이 흔하고, 원본(`limits.<축>
.requires_accessory`)에는 그 표시가 있었다. 반입이 그것을 버려 본체 값처럼 들어왔고, 검색이
갖고 있지도 않은 챔버를 전제로 「80 °C 됨」 이라고 답할 자리였다 — ADR 0003 이 막으려던
바로 그 오답. 표시를 세 표에 두고 검색이 판정을 가른다(`accessory`).

Revision ID: 0017_requires_accessory
Revises: 0016_term_code_unique
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_requires_accessory"
down_revision = "0016_term_code_unique"
branch_labels = None
depends_on = None

TABLES = ("model_spec_values", "series_test_conditions", "equipment_test_conditions")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "requires_accessory", sa.Boolean(), server_default="false", nullable=False
            ),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "requires_accessory")
