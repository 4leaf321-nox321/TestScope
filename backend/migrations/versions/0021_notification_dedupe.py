"""알림의 중복 방지 키 — `notifications.dedupe_key`.

교정 만료 알림은 사람이 무언가를 해서 생기는 것이 아니라 **날이 되면** 생기는 것이라
훑기(sweep)가 만든다. 훑기는 여러 번 돌고, 같은 장비의 같은 만료일에 알림이 두 번
가면 사람은 곧 알림을 안 읽는다. 사람마다 같은 키는 한 번만 — 부분 유일 색인이 그것을
DB 에서 막는다(코드가 확인하고 넣는 사이에 다른 요청이 끼어도).

Revision ID: 0021_notification_dedupe
Revises: 0020_test_item_condition_keys
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_notification_dedupe"
down_revision = "0020_test_item_condition_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("dedupe_key", sa.String(200), nullable=True))
    op.create_index(
        "uq_notifications_user_dedupe",
        "notifications",
        ["user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_user_dedupe", table_name="notifications")
    op.drop_column("notifications", "dedupe_key")
