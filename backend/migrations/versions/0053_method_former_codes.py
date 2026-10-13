"""규격에 **옛 번호** — 시스템 관리자가 번호를 고쳐도 옛 번호로 찾아온다.

규격 번호를 고칠 길이 없었다(제목만 고쳐졌다 — 2026-10-13 사용자 보고). 그런데 번호만 바꾸면
번호를 열쇠로 쓰는 곳이 전부 그 규격을 잃는다: 카탈로그 반입은 옛 번호로 같은 규격을 **하나 더
만들고**, 요구 조건 표 반입은 「없는 규격」 이라 하고, 검토함의 규격 물음은 주인 없는 줄이 된다.

    former_codes  고치기 전의 번호들. 반입 · 검토함 · 목록 검색이 이것으로도 그 규격을 찾는다.

Revision ID: 0053_method_former_codes
Revises: 0052_spec_definition_source_keys
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0053_method_former_codes"
down_revision = "0052_spec_definition_source_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_methods",
        sa.Column("former_codes", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("test_methods", "former_codes")
