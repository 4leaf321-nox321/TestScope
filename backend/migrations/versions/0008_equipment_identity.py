"""보유 장비의 속성을 실무가 요구하는 모양으로 다시 세운다.

지금까지 보유 장비는 카탈로그를 가리키는 얇은 껍데기였다 — 자산번호·이름·자리·상태.
현장이 실제로 요구하는 것은 그보다 넓다:

    식별   부서관리번호가 따로 있다. 전사 자산번호와 다른 체계다
    분류   카탈로그에 없는 자작 장비도 「무슨 종류냐」 에는 답해야 한다
    소속   부서는 반드시 있고, 공용인지는 **별개의 사실**이다
    생애   입고·유휴가 실재한다. 제조연도와 폐기일도 묻힌다
    교정   이력만 있고 「대상인가」 가 없어서, 이력 없는 장비가 대상이 아닌 것인지
           빠뜨린 것인지 구별되지 않았다
    사양   카탈로그 값 위에 **실측을 덮을** 자리가 아예 없었다

## 비울 수 없게 만드는 칸이 셋이다

보유 부서·거점·상세위치. 지금 데이터에 빈 것이 있으면 **아무것도 바꾸기 전에**
멈춘다 — 중간에 멈추면 어디까지 갔는지 아무도 모른다.

전에는 보유 부서 NULL 이 「전사 공용」 을 겸했다. 그러면 공용으로 표시하는 순간
관리 부서를 잃는다 — 그래서 `shared_use` 로 칸을 나눈다.

Revision ID: 0008_equipment_identity
Revises: 0007_raw_catalog
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_equipment_identity"
down_revision = "0007_raw_catalog"
branch_labels = None
depends_on = None

#: 비울 수 없게 되는 칸들. 빈 행이 있으면 먼저 채워야 한다.
_REQUIRED = ("owner_workspace_id", "site_term_id", "location")


def _stop_if_empty() -> None:
    """빈 칸이 있으면 **손대기 전에** 멈춘다.

    NOT NULL 을 거는 순간 터지게 두면 앞의 add_column 은 이미 지나간 뒤다. 그 상태를
    사람이 보고 어디까지 갔는지 되짚는 일은, 되짚을 수 있을 때조차 비싸다.
    """
    bind = op.get_bind()
    broken: list[str] = []
    for column in _REQUIRED:
        rows = bind.execute(
            sa.text(
                # 칸 이름은 위 _REQUIRED 상수에서만 온다 — 밖에서 들어오는 값이 아니다.
                f"select asset_no from equipment "
                f"where deleted_at is null and {column} is null order by asset_no limit 20"
            )
        ).fetchall()
        if rows:
            names = ", ".join(row[0] for row in rows)
            broken.append(f"  {column} 이 빈 장비: {names}")
    if broken:
        raise RuntimeError(
            "보유 부서·거점·상세위치는 이제 비울 수 없습니다. 먼저 채우세요:\n"
            + "\n".join(broken)
        )


def upgrade() -> None:
    _stop_if_empty()

    # --- 식별 ---------------------------------------------------------------
    op.add_column("equipment", sa.Column("dept_asset_no", sa.String(50), nullable=True))
    op.create_index("ix_equipment_dept_asset_no", "equipment", ["dept_asset_no"])
    # 유일성은 **부서 안에서만**. 부서마다 자기 번호 체계를 쓴다.
    op.create_unique_constraint(
        "uq_equipment_dept_asset_no", "equipment", ["owner_workspace_id", "dept_asset_no"]
    )

    # --- 분류·제조사 (카탈로그 미연결 장비용) --------------------------------
    op.add_column("equipment", sa.Column("category_term_id", sa.Uuid(), nullable=True))
    op.create_index("ix_equipment_category_term_id", "equipment", ["category_term_id"])
    op.create_foreign_key(
        "fk_equipment_category_term_id_vocabulary_terms",
        "equipment",
        "vocabulary_terms",
        ["category_term_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("equipment", sa.Column("maker_text", sa.String(200), nullable=True))
    op.add_column("equipment", sa.Column("model_text", sa.String(200), nullable=True))

    # --- 소속 ---------------------------------------------------------------
    op.add_column(
        "equipment",
        sa.Column("shared_use", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_equipment_shared_use", "equipment", ["shared_use"])
    op.alter_column("equipment", "owner_workspace_id", nullable=False)
    op.alter_column("equipment", "site_term_id", nullable=False)
    op.alter_column("equipment", "location", type_=sa.String(200), nullable=False)

    # 거점을 지우면 그 장비가 어디 있었는지 알 수 없게 된다 — SET NULL 에서 RESTRICT 로.
    op.drop_constraint(
        "fk_equipment_site_term_id_vocabulary_terms", "equipment", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_equipment_site_term_id_vocabulary_terms",
        "equipment",
        "vocabulary_terms",
        ["site_term_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # --- 생애 ---------------------------------------------------------------
    op.add_column("equipment", sa.Column("manufactured_year", sa.Integer(), nullable=True))
    op.add_column("equipment", sa.Column("retired_on", sa.Date(), nullable=True))

    # --- 교정 ---------------------------------------------------------------
    op.add_column(
        "equipment",
        sa.Column(
            "calibration_required", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.create_index("ix_equipment_calibration_required", "equipment", ["calibration_required"])
    op.add_column(
        "equipment", sa.Column("calibration_interval_months", sa.Integer(), nullable=True)
    )

    # --- 개체 사양 실측값 ----------------------------------------------------
    op.create_table(
        "equipment_spec_values",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "equipment_id",
            sa.Uuid(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "definition_id",
            sa.Uuid(),
            sa.ForeignKey("spec_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("num_value", sa.Float(), nullable=True),
        sa.Column("num_min", sa.Float(), nullable=True),
        sa.Column("num_max", sa.Float(), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("bool_value", sa.Boolean(), nullable=True),
        sa.Column("measured_on", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("spec_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Uuid(),
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
        sa.UniqueConstraint(
            "equipment_id", "definition_id", name="uq_equipment_spec_values_key"
        ),
    )
    for column in ("equipment_id", "definition_id", "source_id"):
        op.create_index(
            f"ix_equipment_spec_values_{column}", "equipment_spec_values", [column]
        )


def downgrade() -> None:
    # **되돌리면 실측이 사라진다.** 카탈로그 값은 카탈로그에 남지만, 우리가 잰 값은
    # 이 표에만 있었다 — 다시 반입해도 돌아오지 않는다.
    op.drop_table("equipment_spec_values")

    op.drop_index("ix_equipment_calibration_required", table_name="equipment")
    op.drop_column("equipment", "calibration_interval_months")
    op.drop_column("equipment", "calibration_required")
    op.drop_column("equipment", "retired_on")
    op.drop_column("equipment", "manufactured_year")

    op.drop_constraint(
        "fk_equipment_site_term_id_vocabulary_terms", "equipment", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_equipment_site_term_id_vocabulary_terms",
        "equipment",
        "vocabulary_terms",
        ["site_term_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("equipment", "location", type_=sa.String(200), nullable=True)
    op.alter_column("equipment", "site_term_id", nullable=True)
    op.alter_column("equipment", "owner_workspace_id", nullable=True)
    op.drop_index("ix_equipment_shared_use", table_name="equipment")
    op.drop_column("equipment", "shared_use")

    op.drop_column("equipment", "model_text")
    op.drop_column("equipment", "maker_text")
    op.drop_constraint(
        "fk_equipment_category_term_id_vocabulary_terms", "equipment", type_="foreignkey"
    )
    op.drop_index("ix_equipment_category_term_id", table_name="equipment")
    op.drop_column("equipment", "category_term_id")

    op.drop_constraint("uq_equipment_dept_asset_no", "equipment", type_="unique")
    op.drop_index("ix_equipment_dept_asset_no", table_name="equipment")
    op.drop_column("equipment", "dept_asset_no")
