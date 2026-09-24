"""신뢰성 시험의 후보와 확정 — **AI 가 올린 것은 사람이 본 뒤에 쓴다.**

신뢰성 시험은 정합성이 값의 전부다. 「-40 ~ 125 degC」 한 칸이 틀리면 그 조건으로 장비를
고르고, 그 장비로 보고서가 나간다. 그런데 AI 는 시험 표준서를 읽어 스물두 칸을 한 번에
채울 수 있다 — 빠르지만, 틀려도 그만큼 빠르다.

그래서 **기계 자격(PAT)으로 들어온 쓰기는 후보가 된다.** 사람이 화면에서 읽고 고치고
확인해야 확정이다. 누가 언제 확인했는지가 남는다 — 반년 뒤 「이 값 누가 보증했어」 에
답할 자리가 그것뿐이다.

기존 줄은 전부 확정으로 둔다(`server_default`) — 사람이 화면에서 넣은 것들이다.

Revision ID: 0032_reliability_review
Revises: 0031_attachments
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032_reliability_review"
down_revision = "0031_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reliability_tests",
        # **기본이 확정이다.** 이미 있는 줄은 사람이 넣은 것이고, 새 줄의 후보 여부는
        # 서비스가 「어느 자격으로 들어왔나」 를 보고 정한다.
        sa.Column(
            "status",
            sa.String(length=12),
            nullable=False,
            server_default="confirmed",
        ),
    )
    op.add_column(
        "reliability_tests",
        # 올린 통로 — PAT 이름. 검토하는 사람이 「이거 누가 올린 거야」 를 묻는데,
        # 감사까지 뒤지게 하면 안 묻고 그냥 확인을 누른다.
        sa.Column("submitted_via", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "reliability_tests",
        sa.Column(
            "confirmed_by_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "reliability_tests",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reliability_tests_status", "reliability_tests", ["status"])
    # CHECK 는 autogenerate 가 못 본다 — 손으로 건다.
    op.create_check_constraint(
        "status",
        "reliability_tests",
        "status IN ('candidate','confirmed')",
    )


def downgrade() -> None:
    op.drop_constraint("status", "reliability_tests", type_="check")
    op.drop_index("ix_reliability_tests_status", table_name="reliability_tests")
    op.drop_column("reliability_tests", "confirmed_at")
    op.drop_column("reliability_tests", "confirmed_by_id")
    op.drop_column("reliability_tests", "submitted_via")
    op.drop_column("reliability_tests", "status")
