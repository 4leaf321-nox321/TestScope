"""이 기종만의 사양 — `model_free_specs`.

카탈로그 원본의 사양 키 950종 중 803종이 한 기종에만 나온다. 전부 정의로 세우면 「사양
추가」 목록이 못 쓰게 되고, 버리면 그 기종을 아는 데 필요한 것이 원문 JSON 안에만 남는다.
정의 없이 기종에 직접 붙는 이름·값·단위의 자리를 둔다. 같은 이름이 여러 기종에 쌓이면
사람이 「정의로 세우기」 로 올린다.

Revision ID: 0019_model_free_specs
Revises: 0018_series_pending_methods
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019_model_free_specs"
down_revision = "0018_series_pending_methods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_free_specs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equipment_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(150), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_key", sa.String(120), nullable=True),
        sa.Column("origin", sa.String(10), server_default="manual", nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spec_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("model_id", "source_key", name="uq_model_free_specs_source"),
    )
    op.create_index("ix_model_free_specs_model_id", "model_free_specs", ["model_id"])
    op.create_index("ix_model_free_specs_source_id", "model_free_specs", ["source_id"])


def downgrade() -> None:
    op.drop_table("model_free_specs")
