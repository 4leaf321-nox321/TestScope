"""신뢰성 시험을 가질 수 있는 부서 — **메뉴 표시가 아니라 소유 자격이다.**

`reliability_listed` 는 「사이드바에 이 부서를 올리나」 라는 뜻이었다. 그래서 등록할 때는
아무도 그 값을 안 봤고, 표시가 꺼진 부서에도 시험이 들어갔다 — 개발 DB 에서 실제로
`dx`(DX 부문, 표시 꺼짐)에 한 건이 붙어 있었다.

고치면서 뜻이 바뀐다. 이제 이 값이 **등록을 막는다.** 이름이 「목록에 보이나」 로 남아
있으면 다음 사람이 화장으로 읽고 무심코 끄고, 그러면 그 부서는 등록이 조용히 막힌다.
그래서 이름도 함께 옮긴다.

시험은 **사업부에만** 둔다는 것이 이 표시의 쓰임이다(2026-09-29). 조직도에 「사업부」 라는
층이 따로 없으므로(`workspaces` 에 kind 가 없다) 관리자가 켜 둔 곳이 곧 그 층이다.

Revision ID: 0036_reliability_owner
Revises: 0035_spec_documents
"""

from __future__ import annotations

from alembic import op

revision = "0036_reliability_owner"
down_revision = "0035_spec_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("workspaces", "reliability_listed", new_column_name="reliability_owner")


def downgrade() -> None:
    op.alter_column("workspaces", "reliability_owner", new_column_name="reliability_listed")
