"""조건 키 여덟 — **문서에 늘 나오는데 걸 자리가 없던 것들.**

사내 신뢰성 시험 문서를 옮겨 적다 보니 드러났다(2026-09-30). 조건 축이 없으면 그 줄은
문장으로 남고, **문장은 검색이 못 읽는다** — 「1000h 버티는 챔버 있나」 가 답이 안 나온다.

    duration            유지 시간        1000h · 500h — 시험 이름에 들어가는 값이다
    cycles              사이클 수        500 cycle — 프로파일 한 벌을 몇 번 도나
    pressure            기압            감압·가압
    altitude            고도            문서가 고도로 적으면 환산하지 않는다(환산식이 문서마다 다르다)
    ramp_rate           승온·하강 속도    열충격이 요구하는 변화율 — 챔버가 낼 수 있는 속도가 판정을 가른다
    salt_concentration  염수 농도        보통 5%
    rf_power            RF 입력 전력     dBm 문서는 W 로 옮기고 원문은 note 에
    vswr                VSWR           단위 없는 비(比)

`cycles` 와 `vswr` 은 **차원이 없다** — `chamber` 가 그런 것처럼 빈 문자열로 둔다. 단위
환산이 없다는 뜻이고, 그래서 표시 단위만 사람 말로 적는다(「회」).

Revision ID: 0039_more_condition_keys
Revises: 0038_term_sort_order
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039_more_condition_keys"
down_revision = "0038_term_sort_order"
branch_labels = None
depends_on = None

#: `reference.py` 의 CONDITIONS 와 같은 값이다 — 그쪽은 새 설치용, 여기는 이미 도는 DB 용.
KEYS = [
    (
        "duration",
        "유지 시간",
        "range",
        "time",
        "s",
        "h",
        62,
        "그 조건을 얼마나 버티나. 1000h · 500h 처럼 시험 이름에 들어가는 값이다.",
    ),
    (
        "cycles",
        "사이클 수",
        "range",
        "",
        "",
        "회",
        63,
        "되풀이 횟수. 500 cycle 처럼 프로파일 한 벌을 몇 번 도나 — 단위가 없는 셈이다.",
    ),
    (
        "pressure",
        "기압",
        "range",
        "pressure",
        "Pa",
        "kPa",
        64,
        "감압·가압 시험의 압력. 고도로 적힌 문서는 고도(altitude)에 적는다.",
    ),
    (
        "altitude",
        "고도",
        "range",
        "length",
        "m",
        "m",
        65,
        "항공 수송·고지대 시험. 문서가 고도로 적으면 환산하지 말고 여기에 적는다 —"
        " 환산식이 문서마다 다르고, 옮겨 적는 사람이 그것을 못 고른다.",
    ),
    (
        "ramp_rate",
        "승온·하강 속도",
        "range",
        "temperature_rate",
        "degC/s",
        "degC/min",
        66,
        "열충격·온도 사이클이 요구하는 변화율. 챔버가 낼 수 있는 속도가 판정을 가른다.",
    ),
    (
        "salt_concentration",
        "염수 농도",
        "range",
        "ratio",
        "%",
        "%",
        67,
        "염수 분무 시험의 농도(보통 5%).",
    ),
    (
        "rf_power",
        "RF 입력 전력",
        "range",
        "power",
        "W",
        "W",
        68,
        "RF 시험이 거는 입력. dBm 으로 적힌 문서는 W 로 옮기고 원문을 note 에 남긴다.",
    ),
    (
        "vswr",
        "VSWR",
        "range",
        "",
        "",
        "",
        69,
        "정재파비. 단위가 없는 비(比)라 1.5 : 1 은 1.5 로 적는다.",
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
