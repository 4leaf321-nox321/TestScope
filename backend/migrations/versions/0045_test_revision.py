"""신뢰성 시험이 **규격서의 어느 판**의 것인가 — 판마다 한 벌.

규격서 하나에 시험이 **한 벌만** 붙었다(2026-09-30). 같은 규격서의 개정 14와 18에 이름이
같은 시험이 **70개**, 그중 **36개는 조건이 다른데** 먼저 올라간 판이 이기고 나머지는 409 로
막혔다. 유일성 자리에 판이 없었기 때문이다.

**판마다 시험을 복제한다.** 신뢰성 시험은 수백 건 규모이고 개정이 잦지 않다 — 그 값을
치르면 「이 판의 목록」 이 계산 없이 바로 나온다. 판 사이의 차이를 매번 접어 계산하는 쪽은
목록 한 번 그리는 데 판 수만큼 일이 늘고, 그 계산이 틀리면 어느 판의 조건인지 아무도 모른다.

    document_revision_id   이 줄이 속한 판. 유일성 자리에 들어간다
    introduced_revision_id 이 시험이 **처음 생긴** 판(0043). 이력이지 자리가 아니다

둘을 나눈 이유: 개정 18의 줄도 「개정 14에서 신설」 일 수 있다. 자리는 지금 어느 판의
것인가이고, 이력은 어디서 왔는가다.

**규격서 코드 유일성(부서, 코드)은 그대로 둔다.** 한 문서의 여러 판이 한 줄에 묶여야
이력이 성립한다 — 판마다 문서 줄을 새로 만들면 「이 규격서의 개정들」 이 흩어진다.

Revision ID: 0045_test_revision
Revises: 0044_name_scope
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0045_test_revision"
down_revision = "0044_name_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reliability_tests",
        sa.Column(
            "document_revision_id",
            PgUUID(as_uuid=True),
            # **판을 지워도 시험은 남는다** — 어느 판이었는지를 잃을 뿐이고, 그것 때문에
            # 시험이 사라지면 훨씬 나쁘다(0043 의 다른 두 칸과 같은 규칙).
            sa.ForeignKey("spec_document_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_reliability_tests_document_revision_id",
        "reliability_tests",
        ["document_revision_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reliability_tests_document_revision_id", table_name="reliability_tests")
    op.drop_column("reliability_tests", "document_revision_id")
