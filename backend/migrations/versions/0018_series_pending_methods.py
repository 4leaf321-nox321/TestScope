"""계열이 인용했는데 시험 항목 미정인 규격 — `series_pending_methods`.

카탈로그 객체의 규격 목록은 계열에 평평하게 붙어 온다. 시험이 여럿인 계열이 인용한 규격은
어느 시험의 것인지 반입이 못 정하고, 그동안 「누가 인용했나」 가 DB 어디에도 없었다 —
시험법 464 중 287 이 「가능 장비 없음」 으로 서서, 못 하는 시험과 끊긴 연결을 아무도 못
갈랐다. 여기 남겨 두면 시험 항목이 정해지는 순간 그 계열의 시험 항목에 자동으로 붙는다.

Revision ID: 0018_series_pending_methods
Revises: 0017_requires_accessory
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018_series_pending_methods"
down_revision = "0017_requires_accessory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "series_pending_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equipment_series.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "method_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_methods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("series_id", "method_id", name="uq_series_pending_methods"),
    )
    op.create_index(
        "ix_series_pending_methods_series_id", "series_pending_methods", ["series_id"]
    )
    op.create_index(
        "ix_series_pending_methods_method_id", "series_pending_methods", ["method_id"]
    )


def downgrade() -> None:
    op.drop_table("series_pending_methods")
