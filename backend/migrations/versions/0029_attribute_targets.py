"""속성의 대상을 장비 계열·시험법까지 — 모든 객체 종류에 관리자가 칸을 더할 수 있게.

`attribute_values` 에 `series_id` · `method_id` 대상 열이 늘고, 값이 가리키는 규격 열은
`ref_method_id` 로 이름을 바꾼다(대상 열과 부딪히므로). 기존 값의 `method_id` 는 전부
규격 참조였으니 그대로 옮긴다.

Revision ID: 0029_attribute_targets
Revises: 0028_review_facts
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_attribute_targets"
down_revision = "0028_review_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attribute_values", sa.Column("series_id", sa.UUID(), nullable=True))
    op.add_column("attribute_values", sa.Column("ref_method_id", sa.UUID(), nullable=True))
    # 기존 값의 method_id 는 전부 「값이 가리키는 규격」 이었다 — 참조 열로 옮기고 대상 열은 비운다.
    op.execute("UPDATE attribute_values SET ref_method_id = method_id, method_id = NULL")
    # CHECK 제약은 autogenerate 가 못 본다 — 대상 넷으로 다시 건다.
    op.drop_constraint("target", "attribute_definitions", type_="check")
    op.create_check_constraint(
        "target",
        "attribute_definitions",
        "target IN ('reliability_test','equipment','series','method')",
    )
    op.drop_constraint("one_target", "attribute_values", type_="check")
    op.create_check_constraint(
        "one_target",
        "attribute_values",
        "(reliability_test_id IS NOT NULL)::int + (equipment_id IS NOT NULL)::int"
        " + (series_id IS NOT NULL)::int + (method_id IS NOT NULL)::int = 1",
    )
    op.create_index(
        op.f("ix_attribute_values_method_id"), "attribute_values", ["method_id"], unique=False
    )
    op.create_index(
        op.f("ix_attribute_values_series_id"), "attribute_values", ["series_id"], unique=False
    )
    op.create_index(
        "uq_attribute_values_method",
        "attribute_values",
        ["method_id", "definition_id"],
        unique=True,
        postgresql_where=sa.text("method_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attribute_values_series",
        "attribute_values",
        ["series_id", "definition_id"],
        unique=True,
        postgresql_where=sa.text("series_id IS NOT NULL"),
    )
    op.drop_constraint(
        op.f("fk_attribute_values_method_id_test_methods"),
        "attribute_values",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_attribute_values_method_id_test_methods"),
        "attribute_values",
        "test_methods",
        ["method_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_attribute_values_series_id_equipment_series"),
        "attribute_values",
        "equipment_series",
        ["series_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_attribute_values_ref_method_id_test_methods"),
        "attribute_values",
        "test_methods",
        ["ref_method_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_attribute_values_ref_method_id_test_methods"),
        "attribute_values",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_attribute_values_series_id_equipment_series"),
        "attribute_values",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_attribute_values_method_id_test_methods"),
        "attribute_values",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_attribute_values_method_id_test_methods"),
        "attribute_values",
        "test_methods",
        ["method_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_index(
        "uq_attribute_values_series",
        table_name="attribute_values",
        postgresql_where=sa.text("series_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_attribute_values_method",
        table_name="attribute_values",
        postgresql_where=sa.text("method_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_attribute_values_series_id"), table_name="attribute_values")
    op.drop_index(op.f("ix_attribute_values_method_id"), table_name="attribute_values")
    op.drop_constraint("one_target", "attribute_values", type_="check")
    op.create_check_constraint(
        "one_target",
        "attribute_values",
        "(reliability_test_id IS NOT NULL)::int + (equipment_id IS NOT NULL)::int = 1",
    )
    op.drop_constraint("target", "attribute_definitions", type_="check")
    op.create_check_constraint(
        "target",
        "attribute_definitions",
        "target IN ('reliability_test','equipment')",
    )
    op.execute("UPDATE attribute_values SET method_id = ref_method_id")
    op.drop_column("attribute_values", "ref_method_id")
    op.drop_column("attribute_values", "series_id")
