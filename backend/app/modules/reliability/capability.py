"""이 신뢰성 시험을 **돌릴 수 있는 장비** — 조건 속성이 검색 조건이 된다.

이 시스템의 물음은 결국 하나다: 「이 시험, 우리 조직에서 할 수 있나」. 지금까지 신뢰성
시험은 시험 항목까지만 이어져 있어서 답이 「인장을 하는 장비 12대」 였다 — 그런데 그 시험은
-40 ~ 125 °C 에서 돈다. 12대 중 그 온도를 내는 것이 몇인지는 사람이 장비를 하나씩 열어
봐야 했고, 그 순간 이 시스템은 전화 돌리기를 한 단계 줄였을 뿐 없애지는 못한다.

조건 속성(`kind="condition"`, 정의에 `condition_key_id`)은 **검색축과 같은 축·같은 차원**
으로 적히므로 그대로 검색 조건이 된다. 그래서 여기서는 새 판정 규칙을 만들지 않는다 —
속성을 `ConditionQuery` 로 옮기고 기존 장비 찾기(`search.services.search`)에 넘긴다.
판정 규칙이 두 벌이면 같은 장비를 놓고 검색 화면과 이 화면이 다른 답을 하게 된다.

## 범위는 물음 둘이다

-40 ~ 125 °C 는 「125 이상 올라가나」 와 「-40 이하로 내려가나」 두 물음이다. 하나로 묶으면
125 까지 올라가지만 0 까지밖에 안 내려가는 챔버가 통과한다.

## 못 옮기는 조건은 버리지 않고 말한다

단위를 축의 SI 로 못 바꾸면(표에 없는 단위, 차원이 다른 짝) 그 조건은 **빼고 그렇다고
적는다**(`skipped`). 조용히 빼면 화면은 조건 넷을 다 본 것처럼 「가능」 이라고 답한다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import (
    CapabilityItemOut,
    CapabilityOut,
    SkippedConditionOut,
)
from app.modules.search import services as search_services
from app.modules.search.schemas import ConditionQuery, SearchRequest
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared.units import convert

#: 시험 항목 한 줄에 실을 장비 수. 넘으면 「N대 중 20대」 라고 말한다 — 화면에 백 줄을
#: 쏟아 놓으면 아무도 안 읽고, 그때 목록은 있으나 없으나다.
MAX_HITS_PER_ITEM = 20


def _si(value: float | None, unit: str, key: ConditionKey) -> float | None:
    """속성에 적힌 단위를 축의 SI 로. 못 바꾸면 None — 지어서 옮기지 않는다(ADR 0003)."""
    if value is None:
        return None
    return convert(value, unit or key.si_unit, key.si_unit)


def _conditions(
    db: Session, test_id: uuid.UUID
) -> tuple[list[ConditionQuery], list[SkippedConditionOut]]:
    """조건 속성 → 검색 조건. 범위는 두 물음으로 갈라진다."""
    rows = db.execute(
        select(AttributeValue, AttributeDefinition, ConditionKey)
        .join(AttributeDefinition, AttributeValue.definition_id == AttributeDefinition.id)
        .join(ConditionKey, AttributeDefinition.condition_key_id == ConditionKey.id)
        .where(
            AttributeValue.reliability_test_id == test_id,
            AttributeDefinition.kind == "condition",
        )
        .order_by(AttributeDefinition.sort_order, AttributeDefinition.label)
    ).all()

    queries: list[ConditionQuery] = []
    skipped: list[SkippedConditionOut] = []
    for value, definition, key in rows:
        unit = value.unit or definition.unit
        low = _si(value.num_min, unit, key)
        high = _si(value.num_max, unit, key)
        point = _si(value.num_value, unit, key)
        wrote = any(one is not None for one in (value.num_min, value.num_max, value.num_value))
        if not wrote:
            # 값이 안 적힌 조건은 「제한 없음」 이다. 물을 것이 없다.
            continue
        if low is None and high is None and point is None:
            skipped.append(
                SkippedConditionOut(
                    label=definition.label,
                    reason=f"단위 「{unit}」 를 {key.label} 의 {key.si_unit} 로 못 바꿉니다.",
                )
            )
            continue
        if point is not None:
            queries.append(ConditionQuery(condition_key_id=key.id, at=point))
        if high is not None:
            queries.append(ConditionQuery(condition_key_id=key.id, at_least=high))
        if low is not None:
            queries.append(ConditionQuery(condition_key_id=key.id, at_most=low))
    return queries, skipped


def capability(db: Session, user: User, test: ReliabilityTest) -> CapabilityOut:
    """시험 항목마다 「이 조건으로 이 항목이 되는 장비」.

    부서로 좁히지 않는다 — 이 시스템의 물음은 부서를 가로지르고(옆 부서에 있으면 빌리러
    간다), 어느 부서 것인지는 줄마다 적혀 있다. 대신 **그 시험을 등록한 부서의 장비가
    위로 오게** 두지도 않는다: 순서는 검색과 같은 규칙(확실한 것이 위)이라야 두 화면이
    같은 답으로 읽힌다.
    """
    conditions, skipped = _conditions(db, test.id)
    items = db.execute(
        select(ReliabilityTestItem.test_item_term_id, VocabularyTerm.value)
        .join(VocabularyTerm, ReliabilityTestItem.test_item_term_id == VocabularyTerm.id)
        .where(ReliabilityTestItem.reliability_test_id == test.id)
        .order_by(VocabularyTerm.value)
    ).all()

    out: list[CapabilityItemOut] = []
    for term_id, value in items:
        found = search_services.search(
            db,
            user,
            SearchRequest(test_item_term_id=term_id, conditions=conditions),
        )
        out.append(
            CapabilityItemOut(
                term_id=term_id,
                value=value,
                total=found.total,
                unmet_count=found.unmet_count,
                hits=found.hits[:MAX_HITS_PER_ITEM],
            )
        )
    return CapabilityOut(
        test_id=test.id,
        conditions_asked=len(conditions),
        skipped=skipped,
        items=out,
    )
