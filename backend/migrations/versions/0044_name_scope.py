"""이름 유일성을 (사업부, 이름)에서 **가르는 근거까지** 넓힌다.

실제 자료와 부딪혀 드러났다(2026-09-30). 같은 이름이지만 **적용군이 다른 별개의 시험**이
있고, 제품군마다 제 규격서가 제 판을 갖는다. 사업부 안에서 이름이 유일해야 하니 첫 하나만
들어가고 나머지는 409 로 막혔다 — **634장 중 202장**이 그렇게 흡수됐고, 이름을 선점당한
**17건**은 아예 못 들어왔다. 막은 것이 중복이 아니라 서로 다른 시험이었다.

새 기준은 **(사업부, 이름, 적용군, 규격서)** 다:

    같은 이름 · 적용군 다름     -> 다른 시험
    같은 이름 · 규격서 다름     -> 다른 시험
    같은 이름 · 둘 다 같음      -> 같은 시험
    같은 이름 · 둘 다 안 적힘    -> 가를 근거가 없다. 막는다(예전 그대로)

**DB 가 이것을 못 건다.** 적용군과 규격서는 `attribute_values` 에 있어서, 한 표의 유일
인덱스로 표현이 안 된다. 두 칸을 `reliability_tests` 에 베껴 두면 인덱스를 걸 수 있지만
**베낀 값은 반드시 갈라진다** — 속성을 고치는 길이 여럿이고(화면·MCP·묶음 등록), 그중
하나가 동기화를 잊는 날이 온다. 그래서 유일 인덱스를 **찾기 인덱스로 낮추고**, 판정은
`services._check_name_free` 한 곳에 둔다.

치르는 값: **같은 이름을 동시에 두 번 만들면 둘 다 들어갈 수 있다.** 화면은 사람이 한
번에 하나를 누르고 묶음 등록은 줄을 차례로 커밋하므로 실제로 열리는 창은 좁다. 그 창을
닫으려면 베끼는 수밖에 없고, 그것이 더 비싸다고 봤다.

Revision ID: 0044_name_scope
Revises: 0043_evidence_and_documents
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044_name_scope"
down_revision = "0043_evidence_and_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_reliability_tests_division_name", table_name="reliability_tests")
    op.create_index(
        "ix_reliability_tests_division_name",
        "reliability_tests",
        ["division_term_id", "name"],
    )


def downgrade() -> None:
    # **되돌리면 같은 이름이 둘 이상인 시험을 먼저 정리해야 한다** — 좁은 인덱스가 그것을
    # 못 받는다. 지우지 않고 막는다: 무엇을 버릴지는 사람이 정할 일이다.
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                """
            SELECT count(*) FROM (
                SELECT division_term_id, name FROM reliability_tests
                 WHERE deleted_at IS NULL
                 GROUP BY division_term_id, name HAVING count(*) > 1
            ) AS dup
            """
            )
        )
        .scalar()
    )
    if duplicates:
        raise RuntimeError(
            f"같은 사업부에 같은 이름인 시험이 {duplicates}묶음 있습니다 —"
            " 먼저 합치거나 이름을 가른 뒤 되돌리십시오."
        )
    op.drop_index("ix_reliability_tests_division_name", table_name="reliability_tests")
    op.create_index(
        "uq_reliability_tests_division_name",
        "reliability_tests",
        ["division_term_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
