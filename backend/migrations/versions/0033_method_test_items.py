"""규격 ↔ 시험 항목을 **N:M 으로** — 규격 하나가 시험 항목 여럿을 덮는다.

칸 하나(`test_methods.test_item_term_id`)로는 표현할 수 없던 것이 있다. IEC 60529 는
IP 코드의 1자리(방진)와 2자리(방수)를 한 문서가 정의하는데, 칸이 하나뿐이라 「분진 침투」
에 붙이면 「방수(IPX)」 는 **규격이 없는 항목**이 된다 — 그 항목으로 장비를 찾는 사람은
「그런 규격이 없다」 는 답을 받는다(실측 2026-09-24: 규격 0건인 시험 항목 19개 중 여럿이
이 부류였다).

흔한 모양이다. MIL-STD-810 은 방법 번호마다 다른 시험이고, IEC 60068-2 계열도 한 문서가
여러 조건을 담는다.

**칸은 지운다.** 남겨 두면 진실이 두 곳에 있게 되고, 어느 쪽이 맞는지 아무도 모른다.

Revision ID: 0033_method_test_items
Revises: 0032_reliability_review
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033_method_test_items"
down_revision = "0032_reliability_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_method_items",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "method_id",
            sa.UUID(),
            sa.ForeignKey("test_methods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "test_item_term_id",
            sa.UUID(),
            sa.ForeignKey("vocabulary_terms.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index("ix_test_method_items_method_id", "test_method_items", ["method_id"])
    op.create_index(
        "ix_test_method_items_test_item_term_id", "test_method_items", ["test_item_term_id"]
    )
    # 모델이 `UniqueConstraint` 라 **제약**으로 건다 — 유일 인덱스로 만들면
    # `alembic check` 가 매번 어긋남을 말한다(0031 에서 겪은 것의 반대 방향).
    op.create_unique_constraint(
        "uq_test_method_items_pair",
        "test_method_items",
        ["method_id", "test_item_term_id"],
    )
    # **먼저 옮기고 나서 지운다.** 순서가 바뀌면 375건의 연결이 사라진다.
    op.execute(
        """
        INSERT INTO test_method_items (id, method_id, test_item_term_id)
        SELECT gen_random_uuid(), id, test_item_term_id
        FROM test_methods
        WHERE test_item_term_id IS NOT NULL
        """
    )
    op.drop_index("ix_test_methods_test_item_term_id", table_name="test_methods")
    op.drop_column("test_methods", "test_item_term_id")


def downgrade() -> None:
    op.add_column("test_methods", sa.Column("test_item_term_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "test_methods_test_item_term_id_fkey",
        "test_methods",
        "vocabulary_terms",
        ["test_item_term_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_test_methods_test_item_term_id", "test_methods", ["test_item_term_id"]
    )
    # 여럿이던 것은 **하나만** 돌아온다 — 되돌리면 정보가 준다.
    op.execute(
        """
        UPDATE test_methods m
        SET test_item_term_id = (
            SELECT i.test_item_term_id FROM test_method_items i
            WHERE i.method_id = m.id ORDER BY i.test_item_term_id LIMIT 1
        )
        """
    )
    op.drop_table("test_method_items")
