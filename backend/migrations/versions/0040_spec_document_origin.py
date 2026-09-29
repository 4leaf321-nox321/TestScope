"""규격서를 기계가 올릴 수 있게 — **대신 누가 넣었는지 줄에 남긴다.**

`/api/spec-documents` 는 범위 표에 없어서 기계 자격으로 못 썼다. 그래서 AI 는 시험은
올리면서 **그 근거 문서는 못 붙였다** — 값이 틀렸을 때 되짚을 자리가 없어진다. 규격서는
부서 것이므로 장비·신뢰성 시험과 같은 범위(`equipment:write`)로 연다.

열되 **구별은 남긴다.** 사람이 등록한 것과 AI 가 올린 것이 같아 보이면, 검토하는 사람이
무엇을 더 봐야 하는지 모른다 — 신뢰성 시험의 `submitted_via` 와 같은 자리다.

Revision ID: 0040_spec_document_origin
Revises: 0039_more_condition_keys
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040_spec_document_origin"
down_revision = "0039_more_condition_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spec_documents", sa.Column("submitted_via", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("spec_documents", "submitted_via")
