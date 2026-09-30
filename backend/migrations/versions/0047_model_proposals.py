"""카탈로그 기종 등록 요청 — **못 고르는 쪽에 말할 자리를 준다.**

장비를 등록할 때 카탈로그에 그 기종이 없으면 비워 두게 되어 있다(비슷한 기종을 고르면 그
장비의 하중·온도가 남의 것이 되므로, 비워 두라는 안내가 맞다). 그런데 비워 둔 다음에는
**왜 비었는지가 아무 데도 안 남는다** — 제조사·모델명을 글자로 적어 두긴 하지만 그것은
표시용이고, 시스템 관리자는 미연결 목록에서 그 글자를 보고 짐작하는 수밖에 없었다.

카탈로그 정본을 아무나 못 고치는 것은 지켜야 한다(기종을 고르면 그 계열의 시험 항목이
복사되고 조건 판정이 그 사양을 쓴다 — 아무나 세운 기종은 잘못된 답의 근거가 된다). 그래서
시험 항목 제안(`test_item_proposals`, 0043)과 **같은 모양**으로 둔다:

    누구나 요청을 남긴다  →  같은 말끼리 모인다  →  관리자가 한 번 정한다
                                                 →  요청한 장비들에 한꺼번에 걸린다

`normalized` 는 제조사와 모델명을 합쳐 띄어쓰기·대소문자를 지운 비교키다. 「Instron
68FM-300」 과 「instron 68fm-300」 이 다른 줄로 서면 관리자가 같은 판단을 두 번 한다.

한 장비가 같은 말을 두 번 내지 않게 (장비, 비교키) 에 유일 제약을 건다 — 반입을 다시
돌리는 일이 흔하고, 그때 줄이 쌓이면 검토 목록의 건수가 거짓이 된다.

Revision ID: 0047_model_proposals
Revises: 0046_value_revisions
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0047_model_proposals"
down_revision = "0046_value_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment_model_proposals",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "equipment_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # 적은 그대로 — **고쳐 쓰지 않는다.** 판단하는 사람이 라벨의 글자를 봐야 카탈로그의
        # 어느 계열인지 정할 수 있다.
        sa.Column("maker_text", sa.String(length=200), nullable=True),
        sa.Column("model_text", sa.String(length=200), nullable=False),
        # 제조사 + 모델명을 합친 비교키. 같은 말이 여러 장비에서 나오면 한 줄로 모인다.
        sa.Column("normalized", sa.String(length=400), nullable=False, index=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "model_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("equipment_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_via", sa.String(length=100), nullable=True),
        sa.Column(
            "created_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.UniqueConstraint(
            "equipment_id", "normalized", name="uq_equipment_model_proposals_pair"
        ),
    )


def downgrade() -> None:
    op.drop_table("equipment_model_proposals")
