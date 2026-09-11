"""물성 ↔ 시험 항목 N:M 표, 그리고 값 code 를 120자로.

검색 사슬 앞에 물성 한 칸을 더 붙인다:

    물성  ⇄  시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치

물성은 기준정보 축 `property` 의 값이고(축은 `reference.py` 가 심는다 — 행은 마이그레이션에
안 넣는다), 그 값의 `code` 가 MaterialTwin 키다. 가장 긴 키가
`mechanical.fatigue_strength_coefficient_normalized`(50자)라 50자 칸에 딱 걸린다 — 120 으로
넓힌다. 좁히는 쪽은 잘라내야 하므로 되돌리지 않는다.

Revision ID: 0014_test_item_properties
Revises: 0013_test_items_rename
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_test_item_properties"
down_revision = "0013_test_items_rename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "vocabulary_terms",
        "code",
        existing_type=sa.String(50),
        type_=sa.String(120),
        existing_nullable=True,
    )
    op.create_table(
        "test_item_properties",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "test_item_term_id",
            sa.Uuid(),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "property_term_id",
            sa.Uuid(),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="suggested", nullable=False),
        sa.Column("source", sa.String(20), server_default="manual", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "confirmed_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "test_item_term_id", "property_term_id", name="uq_test_item_properties_pair"
        ),
    )
    for column in ("test_item_term_id", "property_term_id", "status"):
        op.create_index(f"ix_test_item_properties_{column}", "test_item_properties", [column])


def downgrade() -> None:
    op.drop_table("test_item_properties")
