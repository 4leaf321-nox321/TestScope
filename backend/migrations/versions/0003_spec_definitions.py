"""사양의 정의는 통제하고, 값은 행으로 쌓는다.

사양 어휘는 장비 분류마다 갈리지만 공통도 실재한다. 분류마다 표를 나누면 공통 칸이
복제되고, 한 표에 칸으로 늘어놓으면 분류가 늘 때마다 스키마가 바뀐다. 그래서 정의를
표로 통제하고(spec_definitions) 값은 행으로 둔다(model_spec_values) — ADR 0005.

spec_definition_categories에 행이 없는 정의는 **모든 분류에 공통**이다. 비어 있음을
"아직 안 정했음"이 아니라 "전부"로 읽는다는 뜻이라, 정의를 만들 때 분류를 고르지
않는 쪽이 기본값이 된다.

Revision ID: 0003_spec_definitions
Revises: 0002_equipment_catalog
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_spec_definitions"
down_revision = "0002_equipment_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 사양을 묶는 갈래 — 성능/전원/치수 같은 것.
    op.create_table(
        "spec_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_groups")),
    )
    op.create_index(op.f("ix_spec_groups_slug"), "spec_groups", ["slug"], unique=True)
    # 어떤 사양이 존재하는지. condition_key_id가 있으면 그 값은 검색 축이 된다.
    op.create_table(
        "spec_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=10), server_default="number", nullable=False),
        sa.Column("dimension", sa.String(length=30), server_default="", nullable=False),
        sa.Column("si_unit", sa.String(length=20), server_default="", nullable=False),
        sa.Column("display_unit", sa.String(length=20), server_default="", nullable=False),
        sa.Column(
            "choices",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("condition_key_id", sa.UUID(), nullable=True),
        sa.Column("reflect_as", sa.String(length=5), server_default="max", nullable=False),
        sa.Column("help", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["condition_key_id"],
            ["condition_keys.id"],
            name=op.f("fk_spec_definitions_condition_key_id_condition_keys"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["spec_groups.id"],
            name=op.f("fk_spec_definitions_group_id_spec_groups"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_definitions")),
    )
    op.create_index(
        op.f("ix_spec_definitions_condition_key_id"),
        "spec_definitions",
        ["condition_key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_spec_definitions_group_id"), "spec_definitions", ["group_id"], unique=False
    )
    op.create_index(op.f("ix_spec_definitions_key"), "spec_definitions", ["key"], unique=True)
    # 정의가 어느 장비 분류에 붙는지. 행이 없으면 공통.
    op.create_table(
        "spec_definition_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("category_term_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_term_id"],
            ["vocabulary_terms.id"],
            name=op.f("fk_spec_definition_categories_category_term_id_vocabulary_terms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["spec_definitions.id"],
            name=op.f("fk_spec_definition_categories_definition_id_spec_definitions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_definition_categories")),
        sa.UniqueConstraint(
            "definition_id", "category_term_id", name="uq_spec_definition_category"
        ),
    )
    op.create_index(
        op.f("ix_spec_definition_categories_category_term_id"),
        "spec_definition_categories",
        ["category_term_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_spec_definition_categories_definition_id"),
        "spec_definition_categories",
        ["definition_id"],
        unique=False,
    )
    # 값의 출처가 된 제조사 문서. 어디서 왔는지 못 대면 사양은 소문이다.
    op.create_table(
        "spec_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("maker_term_id", sa.UUID(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["maker_term_id"],
            ["vocabulary_terms.id"],
            name=op.f("fk_spec_sources_maker_term_id_vocabulary_terms"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spec_sources")),
    )
    op.create_index(
        op.f("ix_spec_sources_maker_term_id"), "spec_sources", ["maker_term_id"], unique=False
    )
    op.create_index(op.f("ix_spec_sources_path"), "spec_sources", ["path"], unique=True)
    op.create_index(op.f("ix_spec_sources_sha256"), "spec_sources", ["sha256"], unique=False)
    # 모델 하나의 사양 값. 종류에 따라 채우는 칸이 다르다.
    op.create_table(
        "model_spec_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("num_value", sa.Float(), nullable=True),
        sa.Column("num_min", sa.Float(), nullable=True),
        sa.Column("num_max", sa.Float(), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("bool_value", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["spec_definitions.id"],
            name=op.f("fk_model_spec_values_definition_id_spec_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["equipment_models.id"],
            name=op.f("fk_model_spec_values_model_id_equipment_models"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["spec_sources.id"],
            name=op.f("fk_model_spec_values_source_id_spec_sources"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_spec_values")),
        sa.UniqueConstraint("model_id", "definition_id", name="uq_model_spec_values_key"),
    )
    op.create_index(
        op.f("ix_model_spec_values_definition_id"),
        "model_spec_values",
        ["definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_spec_values_model_id"), "model_spec_values", ["model_id"], unique=False
    )
    op.create_index(
        op.f("ix_model_spec_values_source_id"),
        "model_spec_values",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_model_spec_values_source_id"), table_name="model_spec_values")
    op.drop_index(op.f("ix_model_spec_values_model_id"), table_name="model_spec_values")
    op.drop_index(op.f("ix_model_spec_values_definition_id"), table_name="model_spec_values")
    op.drop_table("model_spec_values")
    op.drop_index(op.f("ix_spec_sources_sha256"), table_name="spec_sources")
    op.drop_index(op.f("ix_spec_sources_path"), table_name="spec_sources")
    op.drop_index(op.f("ix_spec_sources_maker_term_id"), table_name="spec_sources")
    op.drop_table("spec_sources")
    op.drop_index(
        op.f("ix_spec_definition_categories_definition_id"),
        table_name="spec_definition_categories",
    )
    op.drop_index(
        op.f("ix_spec_definition_categories_category_term_id"),
        table_name="spec_definition_categories",
    )
    op.drop_table("spec_definition_categories")
    op.drop_index(op.f("ix_spec_definitions_key"), table_name="spec_definitions")
    op.drop_index(op.f("ix_spec_definitions_group_id"), table_name="spec_definitions")
    op.drop_index(op.f("ix_spec_definitions_condition_key_id"), table_name="spec_definitions")
    op.drop_table("spec_definitions")
    op.drop_index(op.f("ix_spec_groups_slug"), table_name="spec_groups")
    op.drop_table("spec_groups")
