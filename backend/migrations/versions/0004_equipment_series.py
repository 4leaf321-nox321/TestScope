"""카탈로그를 두 층으로 나눈다 — 계열(EquipmentSeries)과 기종(EquipmentModel).

한 계열 안에서 하중 용량이 중앙값 60배, 최대 1200배 갈린다. 계열을 카탈로그 한
줄로 두면 0.5 kN 짜리 한 대를 가진 부서가 「300 kN 인장 되나요」 에 된다고
답한다(ADR 0006).

**무슨 시험이 되나는 계열로, 어디까지 되나는 기종의 사양으로.** 그래서
model_capabilities 가 기종이 아니라 계열에 붙는다.

**있던 데이터를 옮긴다.** 기종마다 그 기종 하나짜리 계열을 만들고, 제조사·분류를
계열로 올린 뒤 옛 칸을 지운다 — 지우고 나서 만들면 되돌릴 수 없다.

Revision ID: 0004_equipment_series
Revises: 0003_spec_definitions
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0004_equipment_series"
down_revision = "0003_spec_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 계열 ------------------------------------------------------------
    op.create_table(
        "equipment_series",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "maker_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_ko", sa.String(200), nullable=True),
        sa.Column("normalized", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column(
            "category_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(20), server_default="main", nullable=False),
        sa.Column("drive", sa.String(30), server_default="", nullable=False),
        sa.Column("form_factor", sa.String(40), server_default="", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("spec_note", sa.Text(), nullable=True),
        sa.Column(
            "source_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("spec_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "maker_term_id", "normalized", name="uq_equipment_series_maker_name"
        ),
    )
    op.create_index("ix_equipment_series_maker_term_id", "equipment_series", ["maker_term_id"])
    op.create_index(
        "ix_equipment_series_category_term_id", "equipment_series", ["category_term_id"]
    )
    op.create_index("ix_equipment_series_normalized", "equipment_series", ["normalized"])
    op.create_index("ix_equipment_series_kind", "equipment_series", ["kind"])
    op.create_index("ix_equipment_series_status", "equipment_series", ["status"])
    op.create_index("ix_equipment_series_source_id", "equipment_series", ["source_id"])
    op.create_index("ix_equipment_series_deleted_at", "equipment_series", ["deleted_at"])

    op.create_table(
        "series_relations",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "host_series_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment_series.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "part_series_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment_series.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "host_series_id", "part_series_id", "relation", name="uq_series_relations_triple"
        ),
    )
    op.create_index(
        "ix_series_relations_host_series_id", "series_relations", ["host_series_id"]
    )
    op.create_index(
        "ix_series_relations_part_series_id", "series_relations", ["part_series_id"]
    )
    op.create_index("ix_series_relations_relation", "series_relations", ["relation"])

    # --- 기종에 계열을 단다 ------------------------------------------------
    op.add_column(
        "equipment_models", sa.Column("series_id", PgUUID(as_uuid=True), nullable=True)
    )
    op.add_column("equipment_models", sa.Column("name_ko", sa.String(150), nullable=True))
    op.add_column(
        "equipment_models",
        sa.Column("form_factor", sa.String(40), server_default="", nullable=False),
    )

    # **기종마다 그 기종 하나짜리 계열을 만든다.** 옛 데이터에는 계열이라는 개념이
    # 없었으니 지어낼 근거도 없다 — 사람이 나중에 합치는 편이, 우리가 이름으로
    # 추측해 잘못 묶는 것보다 낫다.
    op.execute(
        sa.text(
            """
            INSERT INTO equipment_series (
                id, maker_term_id, name, normalized, category_term_id,
                status, summary, spec_note, created_by_id, created_at, updated_at, deleted_at
            )
            SELECT id, maker_term_id, name, normalized, category_term_id,
                   status, summary, spec_note, created_by_id, created_at, updated_at, deleted_at
            FROM equipment_models
            """
        )
    )
    # 계열 id 를 기종 id 와 같게 넣었으므로 그대로 가리키면 된다.
    op.execute(sa.text("UPDATE equipment_models SET series_id = id"))
    op.alter_column("equipment_models", "series_id", nullable=False)
    op.create_foreign_key(
        "fk_equipment_models_series_id_equipment_series",
        "equipment_models",
        "equipment_series",
        ["series_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_equipment_models_series_id", "equipment_models", ["series_id"])

    # 제조사·분류는 이제 계열이 갖는다. 두 곳에 두면 반드시 갈린다.
    op.drop_constraint("uq_equipment_models_maker_name", "equipment_models", type_="unique")
    op.drop_index("ix_equipment_models_maker_term_id", table_name="equipment_models")
    op.drop_index("ix_equipment_models_category_term_id", table_name="equipment_models")
    op.drop_column("equipment_models", "maker_term_id")
    op.drop_column("equipment_models", "category_term_id")
    op.create_unique_constraint(
        "uq_equipment_models_series_name", "equipment_models", ["series_id", "normalized"]
    )

    # --- 카탈로그 역량을 계열로 옮긴다 --------------------------------------
    op.add_column(
        "model_capabilities", sa.Column("series_id", PgUUID(as_uuid=True), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE model_capabilities AS c
               SET series_id = m.series_id
              FROM equipment_models AS m
             WHERE m.id = c.model_id
            """
        )
    )
    op.alter_column("model_capabilities", "series_id", nullable=False)
    op.drop_constraint("uq_model_capabilities_triple", "model_capabilities", type_="unique")
    op.drop_index("ix_model_capabilities_model_id", table_name="model_capabilities")
    op.drop_constraint(
        "fk_model_capabilities_model_id_equipment_models",
        "model_capabilities",
        type_="foreignkey",
    )
    op.drop_column("model_capabilities", "model_id")
    op.create_foreign_key(
        "fk_model_capabilities_series_id_equipment_series",
        "model_capabilities",
        "equipment_series",
        ["series_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_model_capabilities_series_id", "model_capabilities", ["series_id"])
    op.create_unique_constraint(
        "uq_model_capabilities_triple",
        "model_capabilities",
        ["series_id", "test_item_term_id", "method_id"],
    )


def downgrade() -> None:
    """되돌린다. **한 계열에 기종이 여럿이면 역량이 갈 곳이 하나로 안 정해진다** —
    그때는 계열의 첫 기종에 붙인다. 되돌린 뒤에 그 사실을 아는 사람이 없을 수
    있으니, 되돌리기 전에 여기를 읽는 것이 맞다."""
    op.add_column(
        "model_capabilities", sa.Column("model_id", PgUUID(as_uuid=True), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE model_capabilities AS c
               SET model_id = m.id
              FROM (
                SELECT DISTINCT ON (series_id) series_id, id
                  FROM equipment_models
                 ORDER BY series_id, created_at, id
              ) AS m
             WHERE m.series_id = c.series_id
            """
        )
    )
    op.execute(sa.text("DELETE FROM model_capabilities WHERE model_id IS NULL"))
    op.alter_column("model_capabilities", "model_id", nullable=False)
    op.drop_constraint("uq_model_capabilities_triple", "model_capabilities", type_="unique")
    op.drop_index("ix_model_capabilities_series_id", table_name="model_capabilities")
    op.drop_constraint(
        "fk_model_capabilities_series_id_equipment_series",
        "model_capabilities",
        type_="foreignkey",
    )
    op.drop_column("model_capabilities", "series_id")
    op.create_foreign_key(
        "fk_model_capabilities_model_id_equipment_models",
        "model_capabilities",
        "equipment_models",
        ["model_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_model_capabilities_model_id", "model_capabilities", ["model_id"])
    op.create_unique_constraint(
        "uq_model_capabilities_triple",
        "model_capabilities",
        ["model_id", "test_item_term_id", "method_id"],
    )

    op.add_column(
        "equipment_models", sa.Column("maker_term_id", PgUUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "equipment_models", sa.Column("category_term_id", PgUUID(as_uuid=True), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE equipment_models AS m
               SET maker_term_id = s.maker_term_id,
                   category_term_id = s.category_term_id
              FROM equipment_series AS s
             WHERE s.id = m.series_id
            """
        )
    )
    op.create_foreign_key(
        "fk_equipment_models_maker_term_id_vocabulary_terms",
        "equipment_models",
        "vocabulary_terms",
        ["maker_term_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_equipment_models_category_term_id_vocabulary_terms",
        "equipment_models",
        "vocabulary_terms",
        ["category_term_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_equipment_models_maker_term_id", "equipment_models", ["maker_term_id"])
    op.create_index(
        "ix_equipment_models_category_term_id", "equipment_models", ["category_term_id"]
    )
    op.drop_constraint("uq_equipment_models_series_name", "equipment_models", type_="unique")
    op.create_unique_constraint(
        "uq_equipment_models_maker_name", "equipment_models", ["maker_term_id", "normalized"]
    )

    op.drop_index("ix_equipment_models_series_id", table_name="equipment_models")
    op.drop_constraint(
        "fk_equipment_models_series_id_equipment_series",
        "equipment_models",
        type_="foreignkey",
    )
    op.drop_column("equipment_models", "series_id")
    op.drop_column("equipment_models", "form_factor")
    op.drop_column("equipment_models", "name_ko")

    op.drop_table("series_relations")
    op.drop_table("equipment_series")
