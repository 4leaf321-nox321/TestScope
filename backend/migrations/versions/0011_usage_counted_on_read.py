"""쓰임 수를 **저장하지 않는다** — 아무도 갱신하지 않던 칸을 지운다.

`vocabulary_terms.usage_count` 는 「이 값을 몇 군데서 쓰나」 를 담기로 한 칸이었다.
그런데 그것을 올리는 코드가 아무 데도 없었다 — 장비 700대와 계열 200개를 들이고도
모든 값이 0 이었다.

**0 인 화면은 거짓말을 한다.** 기준정보에서 값을 지울지 병합할지 정하는 자리가 그
수인데, 전부 0 이면 지워도 되는 값과 안 되는 값이 같아 보인다.

이제 조회할 때 센다(`services._usage_of`) — 축 하나에 GROUP BY 두세 번이고, 가리키는
칸에 인덱스가 있다. **틀린 수를 싸게 얻느니 맞는 수를 그 값에 치른다.** 조건 정의와
사양 정의는 원래 그렇게 세고 있었다: 같은 화면에서 어떤 것은 실측이고 어떤 것은
0 이었던 셈이다.

Revision ID: 0011_usage_counted_on_read
Revises: 0010_drive_axis
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_usage_counted_on_read"
down_revision = "0010_drive_axis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("vocabulary_terms", "usage_count")


def downgrade() -> None:
    # 되돌려도 **값은 0 이다.** 그것이 이 칸의 원래 상태였다 — 채우는 코드가 없었다.
    op.add_column(
        "vocabulary_terms",
        sa.Column("usage_count", sa.Integer(), server_default="0", nullable=False),
    )
