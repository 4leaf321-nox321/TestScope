"""사양 정의에 **반입 원본 키** — 「정의로 세우기」 가 반입에게 「이 키는 이제 여기로」 를 알린다.

「이 기종만의 사양」 을 정의로 세우면 그 줄은 지워지고 값이 정의로 옮겨 간다. 그런데 반입은
원본 키(`stroke_mm_pk_pk`)가 그 정의로 올라간 것을 알 길이 없어서, 다음 반입에서 그 키를
다시 「이 기종만의 사양」 으로 들였다 — 같은 값이 두 자리에 산다(2026-10-08 코드 검토에서 찾음).
원본 키는 정의의 설명 글에만 「원본 키 `…`」 로 남아 있었다.

    source_keys  이 정의로 들어오는 반입 원본 키 목록. 반입이 짝표에 더해 그 키의 값을 이
                 정의에 넣는다(사람 · AI 가 고친 값은 그대로).

**이미 세운 정의는 설명 글에서 키를 읽어 채운다** — 정의로 세우기가 쓰는 글이 정해져 있어서
(`free_specs.promote`) 지어 채우는 것이 아니다.

Revision ID: 0052_spec_definition_source_keys
Revises: 0051_spec_value_origin
"""

from __future__ import annotations

import json
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0052_spec_definition_source_keys"
down_revision = "0051_spec_value_origin"
branch_labels = None
depends_on = None

_PROMOTED = re.compile(r"원본 키 `([^`]+)`")


def upgrade() -> None:
    op.add_column(
        "spec_definitions",
        sa.Column("source_keys", JSONB, nullable=False, server_default="[]"),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, help FROM spec_definitions "
            "WHERE help LIKE '기종 고유 사양에서 승격(원본 키 %'"
        )
    ).fetchall()
    for row_id, help_text in rows:
        found = _PROMOTED.search(help_text or "")
        if found is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE spec_definitions SET source_keys = CAST(:keys AS jsonb) WHERE id = :id"
            ),
            {"keys": json.dumps([found.group(1)]), "id": row_id},
        )


def downgrade() -> None:
    op.drop_column("spec_definitions", "source_keys")
