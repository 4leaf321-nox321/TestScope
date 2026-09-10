"""부서에 설명을, 슬러그에 여유를 — ReportArchive 부서 정보를 담기 위해.

ReportArchive 의 부서 정보 CSV 에는 `description` 이 있고 슬러그가 64자다. 우리가
50자·설명 없음이면 반입에서 **설명이 통째로 버려지고**, 긴 슬러그는 자를지 거절할지를
골라야 한다 — 자르면 키가 달라지고 거절하면 그 부서가 안 들어온다.

Revision ID: 0006_workspace_description
Revises: 0005_token_scopes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_workspace_description"
down_revision = "0005_token_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("description", sa.String(255), server_default="", nullable=False),
    )
    op.alter_column("workspaces", "slug", type_=sa.String(64), existing_type=sa.String(50))


def downgrade() -> None:
    # **넓힌 것을 좁히면 잘린다.** 64자짜리가 이미 들어와 있으면 그 부서의 주소가
    # 바뀌고, 그것을 가리키던 링크는 전부 죽는다 — 되돌리기 전에 길이를 확인한다.
    op.alter_column("workspaces", "slug", type_=sa.String(50), existing_type=sa.String(64))
    op.drop_column("workspaces", "description")
