"""인용 규격을 **문자열에서 표로** 꺼낸다.

카탈로그가 계열마다 인용한 규격이 453건 들어와 있는데, 역량과는 비고 문자열로만
이어져 있었다:

    note = "카탈로그 인용 규격: ASTM D638 · ISO 527"

그래서 시험법 표는 **아무것도 가리키지 않는 목록**이었다 — 「ASTM D638 되는 장비」 를
물으면 문자열을 훑는 수밖에 없고, 판(edition)이 바뀌어도 따라오지 않는다. 검색 사슬의
세 번째 칸이 그 자리다: 시험 항목 -> 요구 조건 -> **시험법** -> 가능한 장비.

옮긴 뒤 비고에서는 그 줄을 지운다. **두 벌로 두면 한쪽만 고쳐진다.** 비고에 다른 말이
함께 적혀 있으면 그 부분만 남긴다 — 사람이 적은 단서를 지우지 않는다.

Revision ID: 0012_cited_methods
Revises: 0011_usage_counted_on_read
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0012_cited_methods"
down_revision = "0011_usage_counted_on_read"
branch_labels = None
depends_on = None

#: 반입이 비고에 적던 머리말. 이 뒤가 규격 코드 목록이다.
_PREFIX = "카탈로그 인용 규격:"


def upgrade() -> None:
    op.create_table(
        "model_capability_methods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "model_capability_id",
            sa.Uuid(),
            sa.ForeignKey("model_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "method_id",
            sa.Uuid(),
            sa.ForeignKey("test_methods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "model_capability_id", "method_id", name="uq_model_capability_methods"
        ),
    )
    for column in ("model_capability_id", "method_id"):
        op.create_index(
            f"ix_model_capability_methods_{column}", "model_capability_methods", [column]
        )

    bind = op.get_bind()
    methods = {
        code: row_id
        for row_id, code in bind.execute(
            sa.text("select id, code from test_methods where deleted_at is null")
        ).all()
    }
    rows = bind.execute(
        sa.text("select id, note from model_capabilities where note is not null")
    ).all()

    linked = 0
    for capability_id, note in rows:
        if _PREFIX not in note:
            continue
        # 비고에 다른 말이 함께 있을 수 있다. 그 줄만 걷어 내고 나머지는 남긴다.
        kept: list[str] = []
        codes: list[str] = []
        for line in note.splitlines():
            if line.strip().startswith(_PREFIX):
                codes += [
                    one.strip() for one in line.split(":", 1)[1].split("·") if one.strip()
                ]
            else:
                kept.append(line)
        for code in codes:
            method_id = methods.get(code)
            if method_id is None:
                # 규격을 못 찾으면 **비고를 지우지 않는다** — 옮기지 못한 것을 조용히
                # 버리면 그 인용은 어디에도 안 남는다.
                kept.append(f"{_PREFIX} {code}")
                continue
            bind.execute(
                sa.text(
                    "insert into model_capability_methods (id, model_capability_id, method_id) "
                    "values (:id, :capability, :method) on conflict do nothing"
                ),
                {"id": uuid.uuid4(), "capability": capability_id, "method": method_id},
            )
            linked += 1
        rest = "\n".join(line for line in kept if line.strip()).strip() or None
        bind.execute(
            sa.text("update model_capabilities set note = :note where id = :id"),
            {"note": rest, "id": capability_id},
        )
    print(f"  인용 규격 {linked}건을 표로 옮겼습니다")


def downgrade() -> None:
    # **되돌리면 비고로 돌아가지 않는다.** 다시 반입하면 채워진다.
    op.drop_table("model_capability_methods")
