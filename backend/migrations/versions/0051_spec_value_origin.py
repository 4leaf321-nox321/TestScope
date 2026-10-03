"""기종 사양 값에 **누가 넣었나** — 기계는 기계가 넣은 값만 말없이 고친다.

v0.47.0 은 「기계 자격은 있는 값을 못 덮는다」 를 **값 전부에** 걸었다. 누가 넣었는지 적는
칸이 없어서, 사람이 운영에서 고쳐 둔 값(인스트론 두 기종의 단위환산)과 AI 가 방금 넣은 값을
가를 수 없었기 때문이다. 그래서 AI 는 제가 넣은 오타 하나도 `replace` 없이는 못 고쳤다.

    origin         manual(사람) · agent(AI — 개인 토큰) · catalog(반입). 비어 있으면 이 칸이
                   생기기 전에 적힌 값 — 누가 넣었는지 모르므로 사람 값처럼 지킨다
    updated_by_id  마지막으로 적은 계정(사람이거나 토큰의 주인)
    updated_via    기계 자격이면 그 토큰 이름

**이미 있는 값은 채우지 않는다.** 반입이 넣은 것과 사람이 고친 것을 지금 와서 가를 근거가
없다 — 지어서 채우면 사람이 고친 값이 「반입」 으로 찍혀 AI 에게 열린다.

Revision ID: 0051_spec_value_origin
Revises: 0050_voc_board
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0051_spec_value_origin"
down_revision = "0050_voc_board"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_spec_values", sa.Column("origin", sa.String(length=10), nullable=True)
    )
    op.add_column(
        "model_spec_values",
        sa.Column("updated_by_id", PgUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_model_spec_values_updated_by_id_users"),
        "model_spec_values",
        "users",
        ["updated_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "model_spec_values", sa.Column("updated_via", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("model_spec_values", "updated_via")
    op.drop_constraint(
        op.f("fk_model_spec_values_updated_by_id_users"),
        "model_spec_values",
        type_="foreignkey",
    )
    op.drop_column("model_spec_values", "updated_by_id")
    op.drop_column("model_spec_values", "origin")
