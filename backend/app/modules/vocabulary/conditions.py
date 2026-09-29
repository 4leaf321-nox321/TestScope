"""조건 정의 — 검색이 묻는 축(ConditionKey). 쓰이는 것은 못 지우고 끈다.

`services.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.methods.models import MethodRequirement
from app.modules.reliability.models import ReliabilityTest
from app.modules.test_items.models import (
    EquipmentTestCondition,
)
from app.modules.vocabulary.models import (
    ConditionKey,
)
from app.modules.vocabulary.schemas import (
    ConditionKeyOut,
    ConditionReachDefinitionOut,
    ConditionReachOut,
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
    return limits + requirements


def condition_out(db: Session, row: ConditionKey) -> ConditionKeyOut:
    return ConditionKeyOut(
        id=row.id,
        key=row.key,
        label=row.label,
        kind=row.kind,
        dimension=row.dimension,
        si_unit=row.si_unit,
        display_unit=row.display_unit,
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

    **단위를 바꾸는 것은 되돌릴 수 없는 부류다.** kN 을 N 으로 고치는 순간, 이미
    저장된 숫자 전부가 다른 값이 된다 — 그때 무엇이 바뀌었는지 물을 자리가 감사
    기록밖에 없다. key 는 아예 못 바꾼다: 코드와 검색이 그 이름을 걸고 있다.
    """
    row = get_condition(db, condition_id)
    before = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }

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

    **구간을 안 나눈다.** 온도를 「-40 이하 / -40~85 / 85 이상」 으로 가르는 근거가 없고,
    축마다 다르다(VSWR 과 낙하 높이를 같은 규칙으로 못 나눈다). 임의로 나눈 구간은 없는
    것보다 나쁘다 — 읽는 사람이 그 경계에 뜻이 있다고 믿는다. 그래서 **몇 건이고 어디까지
    쓰이나**만 답하고, 좁히는 것은 검색으로 넘긴다.

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
            display_unit=key.display_unit,
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
            ReliabilityTest.deleted_at.is_(None),
        )
    ).all()

    tests: set[uuid.UUID] = set()
    valued: set[uuid.UUID] = set()
    unconvertible: set[uuid.UUID] = set()
    low: float | None = None
    high: float | None = None
    for test_id, point, bottom, top, wrote_unit, definition_unit in rows:
        tests.add(test_id)
        numbers = [one for one in (point, bottom, top) if one is not None]
        if not numbers:
            continue
        source = wrote_unit or definition_unit or key.display_unit
        moved = [convert(one, source, key.display_unit) for one in numbers]
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

    return ConditionReachOut(
        condition_key_id=key.id,
        label=key.label,
        display_unit=key.display_unit,
        definitions=[
            ConditionReachDefinitionOut(id=one.id, key=one.key, label=one.label)
            for one in definitions
        ],
        test_count=len(tests),
        valued_count=len(valued),
        unconvertible_count=len(unconvertible - valued),
        low=low,
        high=high,
    )
