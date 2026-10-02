"""판마다 줄 — 그리고 **지난 판은 목록에서 비킨다.**

0046 은 「한 시험은 한 줄, 과거 판은 값에」 로 갔다. 그 약속이 운영에서 깨졌다(2026-10-01):
개정 14(117건)와 18(160건)을 올리니 겹치는 87건이 18 하나로 흡수되고, **내용이 실제로
다른 36건은 개정 14 값이 저장되지 않았다.** 그러면서 묶음 적재는 `merged` 로 세어 성공처럼
보였다 — 버린 것이 어디에도 안 드러났다.

그래서 **판을 다시 줄의 자리로 올린다.** 같은 규격서·이름·적용군이라도 판이 다르면 다른
줄이다. 0045 로 되돌아가는 것처럼 보이지만 그때 못 풀었던 문제 — 「같은 시험이 판 수만큼
줄로 늘어나 목록이 부푼다」 — 를 여기서 함께 푼다:

    superseded_by_id    이 줄을 **밀어낸** 뒤 판의 줄. 비어 있으면 그것이 최신판이다

목록은 기본으로 `superseded_by_id IS NULL` 만 보여 준다 — 사람이 보는 것은 최신판이고,
지난 판은 「과거 판 포함」 으로 펼치거나 `revision=` 으로 그 판을 집어 본다.

## 왜 칸으로 두나 — 계산으로는 못 한다

「이 줄보다 뒤 판의 같은 시험이 있나」 를 질의로 풀려면 **적용군과 규격서를 SQL 에서
알아야** 하는데, 그 둘은 속성 값(`attribute_values`)에 있고 표를 건너뛴다. 줄마다 그것을
읽으면 목록 한 장이 질의 수백 번이 된다.

대신 **아는 자리에서 적는다.** 적재가 이미 「같은 시험인가」 를 판정하므로(`_same_test`),
거기서 한 줄을 적어 두면 목록은 칸 하나만 보면 된다. 0046 에서 `is_current` 를 칸으로
둔 것과 같은 판단이다 — 읽는 쪽이 여럿이고 쓰는 자리는 하나다.

Revision ID: 0049_revision_rows
Revises: 0048_status_reason
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0049_revision_rows"
down_revision = "0048_status_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reliability_tests",
        sa.Column(
            "superseded_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("reliability_tests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # 목록의 기본 조건이라 **모든 조회가 이 칸을 본다.**
    op.create_index(
        "ix_reliability_tests_superseded_by_id",
        "reliability_tests",
        ["superseded_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reliability_tests_superseded_by_id", table_name="reliability_tests")
    op.drop_column("reliability_tests", "superseded_by_id")
