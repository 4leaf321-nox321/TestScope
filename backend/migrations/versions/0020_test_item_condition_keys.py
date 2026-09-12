"""시험 항목 ↔ 조건 축 — `test_item_condition_keys`.

시험 항목마다 뜻이 있는 조건 축(인장 → 하중·속도·온도)이 어디에도 없었다. 검색은 시험
항목을 골라도 축 일곱 개를 다 묻고, 「이 분류의 기종엔 이 사양이 있어야 한다」 를 말할
근거가 없었다. 사람이 정하는 표를 둔다.

Revision ID: 0020_test_item_condition_keys
Revises: 0019_model_free_specs
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_test_item_condition_keys"
down_revision = "0019_model_free_specs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_item_condition_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "test_item_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "condition_key_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("condition_keys.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "test_item_term_id", "condition_key_id", name="uq_test_item_condition_keys"
        ),
    )
    op.create_index(
        "ix_test_item_condition_keys_test_item_term_id",
        "test_item_condition_keys",
        ["test_item_term_id"],
    )
    op.create_index(
        "ix_test_item_condition_keys_condition_key_id",
        "test_item_condition_keys",
        ["condition_key_id"],
    )


def downgrade() -> None:
    op.drop_table("test_item_condition_keys")
