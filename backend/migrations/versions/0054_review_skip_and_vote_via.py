"""검토함 — **보류 사유**와 **의견이 들어온 통로(MCP)**.

보류할 때 메모가 저장되지 않아 나중에 왜 보류했는지 알 수 없었고, MCP 로 남긴 의견이 화면에서
남긴 의견과 구분되지 않았다(2026-10-13 사용자 보고).

    review_proposals.skip_reason   보류 사유(근거 부족 · 전문가 확인 · 원문 확인 · 맞는 답 없음 · 기타)
    review_proposals.skipped_by    누가 보류했나(이름, MCP 면 「(MCP)」)
    review_proposals.skipped_at    언제
    review_votes.submitted_via     기계 자격이면 그 토큰 이름 — 비어 있으면 화면

보류 메모는 기존 `note` 칸에 담는다(결정 메모와 같은 자리 — 결정하면 결정 메모로 바뀐다).

Revision ID: 0054_review_skip_and_vote_via
Revises: 0053_method_former_codes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054_review_skip_and_vote_via"
down_revision = "0053_method_former_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_proposals", sa.Column("skip_reason", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "review_proposals", sa.Column("skipped_by", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "review_proposals",
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "review_votes", sa.Column("submitted_via", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("review_votes", "submitted_via")
    op.drop_column("review_proposals", "skipped_at")
    op.drop_column("review_proposals", "skipped_by")
    op.drop_column("review_proposals", "skip_reason")
