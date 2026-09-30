"""한 시험은 한 줄, 과거 판은 **값에** — 0045 의 판별 복제를 걷는다.

판마다 시험을 복제하니 「이 판의 목록」 은 싸게 나왔지만, **같은 시험이 판 수만큼 줄로
늘어났다.** 고칠 때 어느 줄을 고칠지 사람이 정해야 하고, 장비 판정·검색·색인이 같은
시험을 여러 건으로 센다. 시험의 정체는 판이 아니라 **규격서 + 이름 + 적용군**이다.

그래서 **시험은 한 줄**로 두고 판은 값에 붙인다:

    attribute_values.document_revision_id   이 값이 몇 판 것인가
    attribute_values.is_current             이 자리의 **지금 값**인가

## `is_current` 를 왜 칸으로 두나 — 베끼는 것이 맞는 드문 경우

한 자리(칸·묶음·차례)에 값이 판마다 쌓이므로, 「지금 값」 은 *판 순서가 가장 뒤인 것*이다.
그 판정을 읽는 쪽마다 다시 구현하면 — 거르기·장비 판정·색인 카드·그래프 간선·MCP 병합 —
**그중 하나는 반드시 잊는다.** 잊은 자리는 과거 판의 값으로 검색에 답하고, 틀린 답은
조용하다.

칸으로 두면 읽는 쪽은 `is_current` 한 줄만 더하면 되고, **유일 인덱스가 그 불변식을
DB 에서 보증한다** — 한 자리에 `is_current` 는 하나뿐이다. 앞서 이름 유일성(0044)에서
베끼기를 거절한 것과 다른 판단인데, 이유가 다르다: 그쪽은 **다른 표**의 값을 베끼는
것이라 고치는 길이 여럿이었고, 이쪽은 같은 표 안이고 **쓰는 자리가 `set_values` 하나**다.

## 인덱스 둘

    uq_attribute_values_reliability        (시험, 칸, 묶음, 차례) WHERE is_current
                                           -> 지금 값은 자리마다 하나
    uq_attribute_values_revision           (시험, 칸, 묶음, 차례, 판)
                                           -> 한 판이 같은 자리에 두 값을 못 쓴다

Revision ID: 0046_value_revisions
Revises: 0045_test_revision
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0046_value_revisions"
down_revision = "0045_test_revision"
branch_labels = None
depends_on = None

#: 판이 없는 값을 인덱스에서 하나로 세기 위한 자리(널끼리는 서로 다르다고 보므로).
NO_REVISION = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    op.add_column(
        "attribute_values",
        sa.Column(
            "document_revision_id",
            PgUUID(as_uuid=True),
            # **판을 지워도 값은 남는다** — 몇 판 것인지를 잃을 뿐이고, 그것 때문에 조건이
            # 사라지면 훨씬 나쁘다.
            sa.ForeignKey("spec_document_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "attribute_values",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        op.f("ix_attribute_values_document_revision_id"),
        "attribute_values",
        ["document_revision_id"],
    )

    # 지금 값은 자리마다 하나 — 예전 인덱스를 `is_current` 로 좁힌다.
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
         WHERE reliability_test_id IS NOT NULL AND is_current
        """
    )
    # 한 판이 같은 자리에 두 값을 못 쓴다.
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_attribute_values_revision
            ON attribute_values (
                reliability_test_id,
                definition_id,
                COALESCE(set_label, ''),
                COALESCE(step_order, -1),
                COALESCE(document_revision_id, '{NO_REVISION}'::uuid)
            )
         WHERE reliability_test_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # 과거 판의 값을 먼저 버려야 한다 — 좁은 인덱스가 자리마다 하나만 받는다.
    op.execute("DELETE FROM attribute_values WHERE NOT is_current")
    op.drop_index("uq_attribute_values_revision", table_name="attribute_values")
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
    op.drop_index(
        op.f("ix_attribute_values_document_revision_id"), table_name="attribute_values"
    )
    op.drop_column("attribute_values", "is_current")
    op.drop_column("attribute_values", "document_revision_id")
