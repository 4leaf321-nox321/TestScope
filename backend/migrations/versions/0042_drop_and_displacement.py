"""조건 키 둘 — **길이 계열이 시편 두께·고도뿐이었다.**

낙하 152 cm 도, MLCC 기판 굽힘 1~10 mm 도 걸 자리가 없어 문장으로 남았다. 문장은 검색이
못 읽으므로 「1 m 낙하 되는 장비」 가 답이 안 나온다(2026-09-30).

같은 「길이」 지만 **묻는 물음이 다르다** — 낙하는 「몇 cm 에서 떨어뜨리나」 이고 변위는
「얼마나 휘나」 다. 한 축에 뭉치면 낙하 시험을 묻는 사람에게 굽힘 시험기가 답으로 온다.

    drop_height    낙하 높이   cm 로 적는다(m 로 환산은 서버가)
    displacement   변위       mm. 크로스헤드 속도(얼마나 빨리)와 다른 물음이다

Revision ID: 0042_drop_and_displacement
Revises: 0041_condition_sets
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042_drop_and_displacement"
down_revision = "0041_condition_sets"
branch_labels = None
depends_on = None

#: `reference.py` 의 CONDITIONS 와 같은 값이다 — 그쪽은 새 설치용, 여기는 이미 도는 DB 용.
KEYS = [
    (
        "drop_height",
        "낙하 높이",
        "range",
        "length",
        "m",
        "cm",
        71,
        "낙하·충격 시험의 높이. 문서가 cm 로 적으면 cm 로 적는다 —"
        " 지그 낙하 152 cm 처럼 시험 이름에 들어가는 값이다.",
    ),
    (
        "displacement",
        "변위",
        "range",
        "length",
        "m",
        "mm",
        72,
        "굽힘·처짐이 요구하는 이동량. MLCC 기판 굽힘 1~10 mm 처럼 지그가 낼 수 있는"
        " 변위가 판정을 가른다.",
    ),
]


def upgrade() -> None:
    for key, label, kind, dimension, si_unit, display_unit, order, help_text in KEYS:
        op.execute(
            sa.text(
                """
                INSERT INTO condition_keys
                    (id, key, label, kind, dimension, si_unit, display_unit, sort_order, help)
                SELECT gen_random_uuid(), :key, :label, :kind, :dimension, :si, :display,
                       :order, :help
                 WHERE NOT EXISTS (SELECT 1 FROM condition_keys WHERE key = :key)
                """
            ).bindparams(
                key=key,
                label=label,
                kind=kind,
                dimension=dimension,
                si=si_unit,
                display=display_unit,
                order=order,
                help=help_text,
            )
        )


def downgrade() -> None:
    # **쓰이고 있으면 안 지운다.** 값이 걸린 축을 지우면 그 시험의 조건이 사라진다.
    for key, *_ in KEYS:
        op.execute(
            sa.text(
                """
                DELETE FROM condition_keys
                 WHERE key = :key
                   AND NOT EXISTS (
                        SELECT 1 FROM test_item_condition_keys t
                         WHERE t.condition_key_id = condition_keys.id)
                """
            ).bindparams(key=key)
        )
