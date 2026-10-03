"""조건 정의 — 검색이 묻는 축(ConditionKey). 쓰이는 것은 못 지우고 끈다.

`services.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.methods.models import MethodRequirement
from app.modules.reliability.models import ReliabilityTest
from app.modules.test_items.models import (
    EquipmentTestCondition,
    SeriesTestCondition,
)
from app.modules.vocabulary import unit_change
from app.modules.vocabulary.models import (
    ConditionKey,
)
from app.modules.vocabulary.schemas import (
    ConditionKeyOut,
    ConditionReachDefinitionOut,
    ConditionReachOut,
    ConditionReachValueOut,
)
from app.shared import audit
from app.shared.errors import Conflict, NotFound
from app.shared.units import convert

# --- 조건 정의 ---------------------------------------------------------------


def _condition_usage(db: Session, condition_key_id: uuid.UUID) -> int:
    limits = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentTestCondition)
            .where(EquipmentTestCondition.condition_key_id == condition_key_id)
        )
        or 0
    )
    requirements = (
        db.scalar(
            select(func.count())
            .select_from(MethodRequirement)
            .where(MethodRequirement.condition_key_id == condition_key_id)
        )
        or 0
    )
    # 계열 조건도 이 축의 단위로 숫자를 담는다. 빠져 있어서 「사용 0」 인 축의 단위를 고치면
    # 카탈로그 계열의 조건이 조용히 다른 뜻이 됐다.
    series = (
        db.scalar(
            select(func.count())
            .select_from(SeriesTestCondition)
            .where(SeriesTestCondition.condition_key_id == condition_key_id)
        )
        or 0
    )
    return limits + requirements + series


def _stored_limits(db: Session, condition_key_id: uuid.UUID) -> dict[str, list[Any]]:
    """이 축의 단위로 **숫자가 담긴** 줄 — 장비 조건 · 계열 조건 · 규격 요구.

    단위를 고칠 때 셋을 같이 옮긴다. 하나라도 빠지면 그 표만 옛 단위로 남고, 검색이 셋을
    서로 견주므로 그 차이는 엉뚱한 판정으로만 드러난다. 글자 조건(고른 값)은 단위와 상관없다.
    """
    out: dict[str, list[Any]] = {}
    for name, table in (
        ("장비 조건", EquipmentTestCondition),
        ("계열 조건", SeriesTestCondition),
        ("규격 요구", MethodRequirement),
    ):
        out[name] = list(
            db.scalars(
                select(table).where(
                    table.condition_key_id == condition_key_id,
                    or_(table.min_value.is_not(None), table.max_value.is_not(None)),
                )
            )
        )
    return out


def condition_out(db: Session, row: ConditionKey) -> ConditionKeyOut:
    return ConditionKeyOut(
        id=row.id,
        key=row.key,
        label=row.label,
        kind=row.kind,
        dimension=row.dimension,
        si_unit=row.si_unit,
        display_unit=row.display_unit,
        unit=row.unit,
        choices=row.choices,
        help=row.help,
        sort_order=row.sort_order,
        is_active=row.is_active,
        usage_count=_condition_usage(db, row.id),
    )


def list_conditions(db: Session, *, include_inactive: bool) -> list[ConditionKeyOut]:
    stmt = select(ConditionKey)
    if not include_inactive:
        stmt = stmt.where(ConditionKey.is_active.is_(True))
    rows = db.scalars(stmt.order_by(ConditionKey.sort_order, ConditionKey.label))
    return [condition_out(db, row) for row in rows]


def get_condition(db: Session, condition_id: uuid.UUID) -> ConditionKey:
    found = db.get(ConditionKey, condition_id)
    if found is None:
        raise NotFound("TSC-VOCAB-0008", "조건 정의를 찾을 수 없습니다.")
    return found


def create_condition(db: Session, *, payload: dict[str, Any]) -> ConditionKey:
    if db.scalar(select(ConditionKey).where(ConditionKey.key == payload["key"])) is not None:
        raise Conflict("TSC-VOCAB-0009", f"이미 있는 조건 키입니다: {payload['key']}")
    row = ConditionKey(**payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_condition(
    db: Session, *, condition_id: uuid.UUID, changes: dict[str, Any], actor: User
) -> ConditionKey:
    """조건 정의를 고친다.

    **단위를 바꾸면 이미 저장된 숫자 전부의 뜻이 바뀐다** — kN 을 N 으로 고치는 순간 20 이
    20 N 이 된다. 그래서 숫자가 있으면 어떻게 할지(`stored_values`: convert · keep)를 말하게
    하고, 안 말하면 409 로 어느 표에 몇 줄인지 준다(`unit_change`). 그 선택도 감사에 남는다.
    key 는 아예 못 바꾼다: 코드와 검색이 그 이름을 걸고 있다.
    """
    row = get_condition(db, condition_id)
    stored_values = changes.pop("stored_values", None)
    before = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }

    # **고치기 전에 묻는다.** 바꿔 놓고 거절하면 세션에 반쯤 고친 줄이 남는다.
    unit_before = row.unit
    display = changes.get("display_unit")
    si = changes.get("si_unit")
    unit_after = (row.display_unit if display is None else display) or (
        row.si_unit if si is None else si
    )
    stored = _stored_limits(db, row.id)
    mode = unit_change.decide(
        what=f"조건 축 「{row.label}」",
        before=unit_before,
        after=unit_after,
        counts={name: len(rows) for name, rows in stored.items()},
        stored_values=stored_values,
        ask_code="TSC-VOCAB-0017",
        cannot_code="TSC-VOCAB-0018",
    )
    if mode == "convert":
        for rows in stored.values():
            for one in rows:
                one.min_value = unit_change.moved(one.min_value, unit_before, unit_after)
                one.max_value = unit_change.moved(one.max_value, unit_before, unit_after)

    for field, value in changes.items():
        if value is not None:
            setattr(row, field, value)
    after = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }
    diff = audit.diff(before, after)
    if mode is not None:
        diff["stored_values"] = {
            "before": None,
            "after": f"{mode} · {sum(len(rows) for rows in stored.values())}줄",
        }
    if diff:
        audit.record(
            db,
            action=audit.CONDITION_KEY_CHANGED,
            actor=actor,
            target_table="condition_keys",
            target_id=row.id,
            target_label=row.label,
            changes=diff,
        )
    db.commit()
    db.refresh(row)
    return row


def condition_reach(db: Session, condition_key_id: uuid.UUID) -> ConditionReachOut:
    """이 조건 축이 **신뢰성 시험에서 얼마나, 어디까지 쓰이나.**

    온톨로지 쪽에서 축을 열면 「이 조건을 거는 시험」 까지는 보이는데 **값이 안 보였다.**
    그래서 읽는 사람은 「-40 °C 이하인 시험」 을 물으려다 막히고, 이 플랫폼이 그걸 못
    한다고 읽었다 — 실제로는 검색(`attr`)이 답하는 물음인데 그 경계가 화면에 없었다.

    **구간을 미리 안 나눈다.** 온도를 「-40 이하 / -40~85 / 85 이상」 으로 가르는 근거가 없고,
    축마다 다르다(VSWR 과 낙하 높이를 같은 규칙으로 못 나눈다). 임의로 나눈 구간은 없는
    것보다 나쁘다 — 읽는 사람이 그 경계에 뜻이 있다고 믿는다. 그래서 **몇 건이고 어디까지
    쓰이나**, 그리고 **실제로 적힌 값**(`common_values`)을 답한다 — 「쓰다 보면 경계가
    드러난다」 를 화면이 그대로 보여 주는 것이다. 좁히는 것은 검색으로 넘긴다.

    **지금 값 · 최신판만 센다.** 지난 판의 값이 섞이면 이제 아무도 안 쓰는 85 °C 가 「자주
    적힌 값」 으로 선다 — 장비 판정(0046)·목록(0049)과 같은 규칙이다.

    `definitions` 가 그 넘김의 열쇠다 — `attr` 이 받는 것은 조건 축 id 가 아니라 속성
    정의의 `key` 라, 화면이 링크를 만들려면 이것이 있어야 한다.
    """
    key = get_condition(db, condition_key_id)
    definitions = list(
        db.scalars(
            select(AttributeDefinition).where(
                AttributeDefinition.condition_key_id == condition_key_id,
                AttributeDefinition.target == "reliability_test",
                AttributeDefinition.kind == "condition",
                AttributeDefinition.status == "standard",
                AttributeDefinition.is_active.is_(True),
            )
        )
    )
    if not definitions:
        return ConditionReachOut(
            condition_key_id=key.id,
            label=key.label,
            display_unit=key.unit,
            definitions=[],
            test_count=0,
            valued_count=0,
            unconvertible_count=0,
            low=None,
            high=None,
        )

    rows = db.execute(
        select(
            AttributeValue.reliability_test_id,
            AttributeValue.num_value,
            AttributeValue.num_min,
            AttributeValue.num_max,
            AttributeValue.unit,
            AttributeDefinition.unit,
        )
        .join(AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id)
        .join(ReliabilityTest, ReliabilityTest.id == AttributeValue.reliability_test_id)
        .where(
            AttributeValue.definition_id.in_([one.id for one in definitions]),
            AttributeValue.is_current.is_(True),
            ReliabilityTest.deleted_at.is_(None),
            ReliabilityTest.superseded_by_id.is_(None),
        )
    ).all()

    tests: set[uuid.UUID] = set()
    valued: set[uuid.UUID] = set()
    unconvertible: set[uuid.UUID] = set()
    low: float | None = None
    high: float | None = None
    #: 값마다 그 값을 적은 시험. 열두 자리에서 맞춘다 — 환산을 거친 85 와 84.99999999 가
    #: 다른 값으로 갈리면 한 경계가 둘로 쪼개진다.
    by_value: dict[float, set[uuid.UUID]] = {}
    for test_id, point, bottom, top, wrote_unit, definition_unit in rows:
        tests.add(test_id)
        numbers = [one for one in (point, bottom, top) if one is not None]
        if not numbers:
            continue
        source = wrote_unit or definition_unit or key.unit
        moved = [convert(one, source, key.unit) for one in numbers]
        if any(one is None for one in moved):
            # **못 바꾼 값은 범위에 안 넣는다.** 틀린 자리에 놓느니 안 보이는 편이 낫고,
            # 몇 건이 그랬는지는 따로 센다 — 안 세면 「그만큼만 쓰인다」 로 읽힌다.
            unconvertible.add(test_id)
            continue
        valued.add(test_id)
        for one in moved:
            assert one is not None
            low = one if low is None else min(low, one)
            high = one if high is None else max(high, one)
            by_value.setdefault(float(f"{one:.12g}"), set()).add(test_id)

    # 많이 적힌 것부터, 같으면 작은 값부터 — **늘 같은 순서**라야 두 번 연 화면이 같다.
    ranked = sorted(by_value.items(), key=lambda pair: (-len(pair[1]), pair[0]))[
        :COMMON_VALUES
    ]
    single = definitions[0] if len(definitions) == 1 else None
    common = [
        ConditionReachValueOut(
            value=value, count=len(ids), attr=_attr_for(single, value, key) if single else None
        )
        for value, ids in ranked
    ]

    return ConditionReachOut(
        condition_key_id=key.id,
        label=key.label,
        display_unit=key.unit,
        definitions=[
            ConditionReachDefinitionOut(id=one.id, key=one.key, label=one.label)
            for one in definitions
        ],
        test_count=len(tests),
        valued_count=len(valued),
        unconvertible_count=len(unconvertible - valued),
        low=low,
        high=high,
        common_values=common,
    )


#: 「자주 적힌 값」 을 몇 개까지 — 칩 열두 개면 한 줄 반이다. 그 뒤는 검색이 답한다.
COMMON_VALUES = 12


def _attr_for(definition: AttributeDefinition, value: float, key: ConditionKey) -> str | None:
    """목록의 `attr` 물음 — **그 칸의 단위로.** 필터는 정의의 단위로 견주므로(`filters`),
    축의 단위로 적으면 칸과 축의 단위가 다를 때 자릿수가 틀린 링크가 된다. 못 바꾸면 링크를
    안 만든다."""
    moved = convert(value, key.unit, definition.unit or key.unit)
    if moved is None:
        return None
    # 열두 자리 — `:g` 의 여섯 자리면 1234567 이 1.23457e+06 이 되어 다른 값을 묻는다.
    return f"{definition.key}={moved:.12g}"
