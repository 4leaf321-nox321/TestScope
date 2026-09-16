"""항목 정의·값 — `attribute_definitions` · `attribute_values`.

신뢰성 시험(뒤에는 보유 장비)에 붙는 칸을 열이 아니라 **행**으로 둔다. 무슨 칸이 필요한지
조사 중이라 열을 미리 뚫을 수 없고, 뚫으면 안 쓰는 열이 남는다. 정의는 초안(draft)과
정식(standard)으로 나뉘고, 초안은 값을 적는 사람이 새 이름을 쓰면 자동으로 생긴다.
값은 종류별로 칸을 나눠 저장하고 단위는 값에 남긴다.

Revision ID: 0027_attributes
Revises: 0026_jobs
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027_attributes"
down_revision = "0026_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attribute_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("kind", sa.String(length=10), server_default="text", nullable=False),
        sa.Column("unit", sa.String(length=20), server_default="", nullable=False),
        sa.Column(
            "choices",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("condition_key_id", sa.UUID(), nullable=True),
        sa.Column("vocabulary_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="draft", nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("help", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("merged_into_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft','standard')", name=op.f("ck_attribute_definitions_status")
        ),
        sa.CheckConstraint(
            "target IN ('reliability_test','equipment')",
            name=op.f("ck_attribute_definitions_target"),
        ),
        sa.ForeignKeyConstraint(
            ["condition_key_id"],
            ["condition_keys.id"],
            name=op.f("fk_attribute_definitions_condition_key_id_condition_keys"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_attribute_definitions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["attribute_definitions.id"],
            name=op.f("fk_attribute_definitions_merged_into_id_attribute_definitions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["vocabulary_id"],
            ["vocabularies.id"],
            name=op.f("fk_attribute_definitions_vocabulary_id_vocabularies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_definitions")),
    )
    op.create_index(
        op.f("ix_attribute_definitions_condition_key_id"),
        "attribute_definitions",
        ["condition_key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attribute_definitions_key"), "attribute_definitions", ["key"], unique=True
    )
    op.create_index(
        op.f("ix_attribute_definitions_target"),
        "attribute_definitions",
        ["target"],
        unique=False,
    )
    op.create_index(
        "uq_attribute_definitions_target_label",
        "attribute_definitions",
        ["target", "label"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "attribute_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("reliability_test_id", sa.UUID(), nullable=True),
        sa.Column("equipment_id", sa.UUID(), nullable=True),
        sa.Column("num_value", sa.Float(), nullable=True),
        sa.Column("num_min", sa.Float(), nullable=True),
        sa.Column("num_max", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=20), server_default="", nullable=False),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("bool_value", sa.Boolean(), nullable=True),
        sa.Column("date_value", sa.Date(), nullable=True),
        sa.Column("term_id", sa.UUID(), nullable=True),
        sa.Column("method_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(reliability_test_id IS NOT NULL)::int + (equipment_id IS NOT NULL)::int = 1",
            name=op.f("ck_attribute_values_one_target"),
        ),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["attribute_definitions.id"],
            name=op.f("fk_attribute_values_definition_id_attribute_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
            name=op.f("fk_attribute_values_equipment_id_equipment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["method_id"],
            ["test_methods.id"],
            name=op.f("fk_attribute_values_method_id_test_methods"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reliability_test_id"],
            ["reliability_tests.id"],
            name=op.f("fk_attribute_values_reliability_test_id_reliability_tests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["term_id"],
            ["vocabulary_terms.id"],
            name=op.f("fk_attribute_values_term_id_vocabulary_terms"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attribute_values")),
    )
    op.create_index(
        op.f("ix_attribute_values_definition_id"),
        "attribute_values",
        ["definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attribute_values_equipment_id"),
        "attribute_values",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attribute_values_reliability_test_id"),
        "attribute_values",
        ["reliability_test_id"],
        unique=False,
    )
    op.create_index(
        "uq_attribute_values_equipment",
        "attribute_values",
        ["equipment_id", "definition_id"],
        unique=True,
        postgresql_where=sa.text("equipment_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attribute_values_reliability",
        "attribute_values",
        ["reliability_test_id", "definition_id"],
        unique=True,
        postgresql_where=sa.text("reliability_test_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_attribute_values_reliability",
        table_name="attribute_values",
        postgresql_where=sa.text("reliability_test_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_attribute_values_equipment",
        table_name="attribute_values",
        postgresql_where=sa.text("equipment_id IS NOT NULL"),
    )
    op.drop_index(
        op.f("ix_attribute_values_reliability_test_id"), table_name="attribute_values"
    )
    op.drop_index(op.f("ix_attribute_values_equipment_id"), table_name="attribute_values")
    op.drop_index(op.f("ix_attribute_values_definition_id"), table_name="attribute_values")
    op.drop_table("attribute_values")
    op.drop_index(
        "uq_attribute_definitions_target_label",
        table_name="attribute_definitions",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_index(op.f("ix_attribute_definitions_target"), table_name="attribute_definitions")
    op.drop_index(op.f("ix_attribute_definitions_key"), table_name="attribute_definitions")
    op.drop_index(
        op.f("ix_attribute_definitions_condition_key_id"), table_name="attribute_definitions"
    )
    op.drop_table("attribute_definitions")
