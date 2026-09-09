"""토큰에 범위를, 감사에 통로를.

MCP 를 붙이기 전에 해 둔다. **나중에 붙이면 이미 발급된 토큰이 전부 전권**이고,
그 토큰들을 회수할 방법은 「전부 폐기」 밖에 없다.

    personal_access_tokens.scopes   이 토큰으로 할 수 있는 일. 기본은 읽기뿐
    audit_entries.actor_client      어느 통로로 들어왔나 (화면 · mcp · 스크립트)
    audit_entries.actor_token       쓴 토큰의 이름

`actor_id` 는 토큰 소유자, 즉 사람이다. 그것만으로는 사람이 넣은 것과 AI 가 넣은
것이 구별되지 않는다.

Revision ID: 0005_token_scopes
Revises: 0004_equipment_series
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_token_scopes"
down_revision = "0004_equipment_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # **기본값이 읽기뿐이다.** 이미 있는 토큰도 여기로 내려온다 — 지금 발급된
    # 것이 하나도 없어서 아무것도 안 깨지고, 앞으로는 쓰기를 명시해야 한다.
    op.add_column(
        "personal_access_tokens",
        sa.Column("scopes", JSONB(), server_default='["read"]', nullable=False),
    )
    op.add_column("audit_entries", sa.Column("actor_client", sa.String(40), nullable=True))
    op.add_column("audit_entries", sa.Column("actor_token", sa.String(100), nullable=True))
    op.create_index("ix_audit_entries_actor_client", "audit_entries", ["actor_client"])


def downgrade() -> None:
    op.drop_index("ix_audit_entries_actor_client", table_name="audit_entries")
    op.drop_column("audit_entries", "actor_token")
    op.drop_column("audit_entries", "actor_client")
    op.drop_column("personal_access_tokens", "scopes")
