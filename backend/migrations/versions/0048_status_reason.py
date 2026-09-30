"""상태 근거 — **왜 그 상태인가.**

보유 장비에는 상태가 여섯이다(입고·가동·유휴·점검·고장·폐기). 그런데 「고장」 이 적혀
있어도 무엇이 고장인지, 「유휴」 가 언제까지 유휴인지가 어디에도 없었다. 그 답은 비고에
섞여 들어갔고, 비고는 온갖 것이 함께 적히는 칸이라 **아무도 그것을 상태의 근거로 안 읽는다.**

그 답이 없으면 할 일이 안 정해진다:

    고장    무엇이 고장인가 · 부품을 기다리나 · 고칠 수 있나
    유휴    과제가 끝나서인가 · 자리를 옮기는 중인가
    폐기    왜 버렸나 — 반년 뒤에 「그 장비 어디 갔냐」 를 묻는 사람이 반드시 있다

## 상태가 바뀌면 근거는 사라진다

칸 하나를 더하면서 지켜야 할 것은 이것 하나다. 「제어보드 고장」 이 적힌 장비를 고쳐서
가동으로 되돌렸는데 그 글이 남아 있으면, 목록은 **가동 중인 장비에 고장 사유를 그려
준다.** 근거는 상태에 붙는 것이지 장비에 붙는 것이 아니다 — `services.update` 가 상태를
바꿀 때 새 근거를 같이 안 받으면 비운다.

Revision ID: 0048_status_reason
Revises: 0047_model_proposals
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048_status_reason"
down_revision = "0047_model_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("equipment", sa.Column("status_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment", "status_reason")
