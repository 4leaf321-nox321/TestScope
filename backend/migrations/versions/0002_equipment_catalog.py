"""장비 카탈로그를 나눈다 — 모델(사양)과 보유 장비(개체).

전에는 equipment 한 표가 둘을 겹쳐 담았다. 제조사·분류·모델명을 카탈로그로 옮기고,
보유 장비는 그것을 가리키게 한다(ADR 0004).

**있던 데이터를 옮긴다.** (제조사, 분류, 모델명) 조합마다 카탈로그 항목을 만들고
그 장비들이 가리키게 한 뒤에 옛 칸을 지운다 — 지우고 나서 만들면 되돌릴 수 없다.

Revision ID: 0002_equipment_catalog
Revises: 0001_initial
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0002_equipment_catalog"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 카탈로그 --------------------------------------------------------
    op.create_table(
        "equipment_models",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "maker_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("normalized", sa.String(150), nullable=False),
        sa.Column(
            "category_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("spec_note", sa.Text, nullable=True),
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
            "maker_term_id", "normalized", name="uq_equipment_models_maker_name"
        ),
    )
    op.create_index("ix_equipment_models_maker_term_id", "equipment_models", ["maker_term_id"])
    op.create_index("ix_equipment_models_normalized", "equipment_models", ["normalized"])
    op.create_index(
        "ix_equipment_models_category_term_id", "equipment_models", ["category_term_id"]
    )
    op.create_index("ix_equipment_models_status", "equipment_models", ["status"])
    op.create_index("ix_equipment_models_deleted_at", "equipment_models", ["deleted_at"])

    op.create_table(
        "model_capabilities",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "test_item_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "method_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("test_methods.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "model_id", "test_item_term_id", "method_id", name="uq_model_capabilities_triple"
        ),
    )
    op.create_index("ix_model_capabilities_model_id", "model_capabilities", ["model_id"])
    op.create_index(
        "ix_model_capabilities_test_item_term_id", "model_capabilities", ["test_item_term_id"]
    )
    op.create_index("ix_model_capabilities_method_id", "model_capabilities", ["method_id"])

    op.create_table(
        "model_capability_limits",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "model_capability_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("model_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "condition_key_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("condition_keys.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("min_value", sa.Float, nullable=True),
        sa.Column("max_value", sa.Float, nullable=True),
        sa.Column("text_value", sa.String(200), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "model_capability_id", "condition_key_id", name="uq_model_capability_limits_key"
        ),
    )
    op.create_index(
        "ix_model_capability_limits_model_capability_id",
        "model_capability_limits",
        ["model_capability_id"],
    )
    op.create_index(
        "ix_model_capability_limits_condition_key_id",
        "model_capability_limits",
        ["condition_key_id"],
    )

    # --- 보유 장비를 카탈로그에 잇는다 ------------------------------------
    op.add_column(
        "equipment",
        sa.Column(
            "model_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment_models.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_equipment_model_id", "equipment", ["model_id"])

    _move_existing()

    # **옮기고 나서 지운다.** 순서가 반대면 되돌릴 수 없다.
    op.drop_index("ix_equipment_category_term_id", table_name="equipment")
    op.drop_index("ix_equipment_manufacturer_term_id", table_name="equipment")
    op.drop_column("equipment", "category_term_id")
    op.drop_column("equipment", "manufacturer_term_id")
    op.drop_column("equipment", "model")


def _move_existing() -> None:
    """있던 장비의 (제조사, 분류, 모델명)을 카탈로그로 올리고 그것을 가리키게 한다.

    **모델명이 없는 장비는 카탈로그를 안 만든다.** 이름 없는 카탈로그 항목을 만들면
    목록이 「(이름 없음)」 으로 채워지고, 그것을 나중에 누가 정리할 수 없다 — 그런
    장비는 `model_id` 가 빈 채로 남아 「카탈로그 미연결」 로 보인다(ADR 0004).

    비교키는 앱의 `shared.text.compare_key` 와 같은 규칙이어야 한다. 여기서 직접
    적는 이유: 마이그레이션은 **그때의 코드**로 남아야 한다 — 앱 코드를 부르면 몇 달
    뒤 그 함수가 바뀌었을 때 이 마이그레이션의 결과가 달라진다.
    """
    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            "SELECT DISTINCT manufacturer_term_id, category_term_id, model "
            "FROM equipment WHERE model IS NOT NULL AND btrim(model) <> ''"
        )
    ).fetchall()

    for maker_id, category_id, raw_model in rows:
        import unicodedata
        import uuid as _uuid

        name = " ".join(str(raw_model).split())
        normalized = unicodedata.normalize("NFKC", name).casefold()
        model_id = _uuid.uuid4()

        connection.execute(
            sa.text(
                "INSERT INTO equipment_models "
                "  (id, maker_term_id, name, normalized, category_term_id, status, summary) "
                "VALUES (:id, :maker, :name, :norm, :category, 'active', :summary) "
                "ON CONFLICT ON CONSTRAINT uq_equipment_models_maker_name DO NOTHING"
            ),
            {
                "id": model_id,
                "maker": maker_id,
                "name": name,
                "norm": normalized,
                "category": category_id,
                "summary": "기존 장비에서 옮겨 온 항목",
            },
        )

        # ON CONFLICT 로 안 들어갔을 수 있다(같은 제조사·모델명이 분류만 다른 경우).
        # 그때는 이미 있는 행을 가리킨다 — 새로 만들면 같은 모델이 둘이 된다.
        found = connection.execute(
            sa.text(
                "SELECT id FROM equipment_models "
                "WHERE normalized = :norm AND maker_term_id IS NOT DISTINCT FROM :maker"
            ),
            {"norm": normalized, "maker": maker_id},
        ).scalar_one()

        connection.execute(
            sa.text(
                "UPDATE equipment SET model_id = :model "
                "WHERE model_id IS NULL "
                "  AND manufacturer_term_id IS NOT DISTINCT FROM :maker "
                "  AND btrim(model) = :name"
            ),
            {"model": found, "maker": maker_id, "name": name},
        )


def downgrade() -> None:
    """**옮긴 값을 되돌려 놓는다.** 표만 지우면 제조사·모델명이 통째로 사라진다."""
    op.add_column("equipment", sa.Column("model", sa.String(100), nullable=True))
    op.add_column(
        "equipment",
        sa.Column(
            "manufacturer_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "equipment",
        sa.Column(
            "category_term_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("vocabulary_terms.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_equipment_manufacturer_term_id", "equipment", ["manufacturer_term_id"])
    op.create_index("ix_equipment_category_term_id", "equipment", ["category_term_id"])

    op.execute(
        sa.text(
            "UPDATE equipment e SET model = m.name, "
            "  manufacturer_term_id = m.maker_term_id, category_term_id = m.category_term_id "
            "FROM equipment_models m WHERE e.model_id = m.id"
        )
    )

    op.drop_index("ix_equipment_model_id", table_name="equipment")
    op.drop_column("equipment", "model_id")
    op.drop_table("model_capability_limits")
    op.drop_table("model_capabilities")
    op.drop_table("equipment_models")
