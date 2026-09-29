"""조건 묶음 — **한 시험에 조건이 한 벌뿐이 아니다.**

값이 칸마다 하나뿐이라(유일 인덱스가 시험+정의) 실제 문서의 조건을 못 담았다. 사내 규격서를
옮겨 적다 드러난 네 모양(2026-09-30):

    동작 -15 ~ 45 °C · 저장 -40 ~ 25 °C         두 벌이 한 벌처럼 쓰인다
    80 °C 80% 120h · 불량 시 70 °C 90% 360h     주 조건과 예외
    -40 · -20 · 25 · 85 °C                      이산 점 넷
    70 °C 1h -> 25 °C 1h -> 30 °C 1h -> 25 °C 1h, 24 cycle   프로파일

넷 다 **묶음(set)과 차례(step)** 두 가지로 담긴다. 새 표를 만들지 않고 값에 두 칸을 붙인 것은,
조건이 결국 「칸 하나에 수치 하나」 이기 때문이다 — 표를 나누면 입력·판정·화면·MCP 가 전부
두 벌이 되고, 그 둘은 반드시 갈라진다.

    set_label   동작 · 저장 · 주 · 불량 시      비우면 이름 없는 한 벌
    step_order  1 · 2 · 3 · 4                비우면 묶음 전체(사이클 수 같은 것)
    step_label  승온 · 유지                   없어도 된다

**사이클 수는 조건 축이다**(0039). 그래서 묶음에 「몇 번 도나」 를 담을 칸을 따로 안 만든다 —
`cycles` 를 step 없이 적으면 그 묶음 전체의 반복이 된다.

유일 인덱스를 (시험, 정의, 묶음, 차례)로 넓힌다. **NULL 끼리는 서로 다르다고 보므로**
COALESCE 로 눌러 둔다 — 안 그러면 이름 없는 묶음의 같은 칸이 여러 줄로 들어와, 예전의
「칸마다 하나」 마저 깨진다.

장비·계열·시험법의 값은 그대로 「칸마다 하나」 다. 묶음은 신뢰성 시험의 조건에만 있다.

Revision ID: 0041_condition_sets
Revises: 0040_spec_document_origin
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041_condition_sets"
down_revision = "0040_spec_document_origin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attribute_values", sa.Column("set_label", sa.String(length=60), nullable=True)
    )
    op.add_column("attribute_values", sa.Column("step_order", sa.Integer(), nullable=True))
    op.add_column(
        "attribute_values", sa.Column("step_label", sa.String(length=60), nullable=True)
    )
    op.create_index(op.f("ix_attribute_values_set_label"), "attribute_values", ["set_label"])
    op.drop_index("uq_attribute_values_reliability", table_name="attribute_values")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_attribute_values_reliability
            ON attribute_values (
                reliability_test_id,
                definition_id,
                COALESCE(set_label, ''),
                COALESCE(step_order, -1)
            )
         WHERE reliability_test_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # 되돌리려면 묶음이 둘 이상인 줄을 먼저 버려야 한다 — 좁은 인덱스가 그것을 못 받는다.
    op.execute(
        "DELETE FROM attribute_values WHERE set_label IS NOT NULL OR step_order IS NOT NULL"
    )
    op.drop_index("uq_attribute_values_reliability", table_name="attribute_values")
    op.create_index(
        "uq_attribute_values_reliability",
        "attribute_values",
        ["reliability_test_id", "definition_id"],
        unique=True,
        postgresql_where=sa.text("reliability_test_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_attribute_values_set_label"), table_name="attribute_values")
    op.drop_column("attribute_values", "step_label")
    op.drop_column("attribute_values", "step_order")
    op.drop_column("attribute_values", "set_label")
