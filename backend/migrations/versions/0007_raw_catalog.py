"""카탈로그 원문을 통째로 보존한다.

정의로 세운 칸은 사양값이 갖는다. 그런데 원본에는 정의가 없는 키가 950종 넘게 있고,
그 값 1,400여 건이 **버려지고 있었다** — 한 카탈로그에만 나오는 것이 대부분이라
정의로 세우면 관리 화면이 죽고, 안 세우면 사라진다.

그래서 둘 다 한다: 아는 것은 사양값으로, 전부는 여기에.

**ADR 0005 의 「JSONB 대신 EAV」 와 어긋나지 않는다.** 거기서 물린 것은 정의를
통제하기 위해서였다(RESTRICT·쓰임 수). 이 칸은 정의하는 자리가 아니라 보존하는
자리다 — 아무것도 이것을 참조하지 않고 검색도 안 본다.

Revision ID: 0007_raw_catalog
Revises: 0006_workspace_description
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_raw_catalog"
down_revision = "0006_workspace_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "equipment_models",
        sa.Column("raw_specs", JSONB(), server_default="{}", nullable=False),
    )
    op.add_column(
        "equipment_series",
        sa.Column("raw_limits", JSONB(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    # **되돌리면 원문이 사라진다.** 다시 반입하면 돌아오지만, 그 사이 원본이
    # 바뀌었으면 돌아오는 것은 지금 것이 아니다.
    op.drop_column("equipment_series", "raw_limits")
    op.drop_column("equipment_models", "raw_specs")
