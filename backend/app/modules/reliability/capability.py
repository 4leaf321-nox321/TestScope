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

단위를 축의 단위(`ConditionKey.unit`)로 못 바꾸면(표에 없는 단위, 차원이 다른 짝) 그
조건은 **빼고 그렇다고 적는다**(`skipped`). 조용히 빼면 화면은 조건 넷을 다 본 것처럼
「가능」 이라고 답한다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import (
    CapabilityItemOut,
    CapabilityOut,
    CapabilitySetOut,
    SkippedConditionOut,
)
from app.modules.search import services as search_services
from app.modules.search.schemas import ConditionQuery, SearchRequest
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared.units import convert

#: 시험 항목 한 줄에 실을 장비 수. 넘으면 「N대 중 20대」 라고 말한다 — 화면에 백 줄을
#: 쏟아 놓으면 아무도 안 읽고, 그때 목록은 있으나 없으나다.
MAX_HITS_PER_ITEM = 20


def _axis(value: float | None, unit: str, key: ConditionKey) -> float | None:
    """속성에 적힌 단위를 **축의 단위**(`key.unit`)로. 못 바꾸면 None — 지어서 옮기지
    않는다(ADR 0003).

    축의 `si_unit` 이 아니다. 장비 조건·판정 글자·검색 화면이 전부 `unit`(display_unit,
    없으면 si_unit)을 쓰는데 여기만 si_unit 으로 옮겨서, 낙하 높이 152 cm 가 1.52(m)가
    되어 「1.52 cm 에서」 로 찍히고 0~100 cm 장비를 통과했다(2026-10-03). 두 단위가 같은
    열여섯 축에서는 안 드러나던 일이다.
    """
    if value is None:
        return None
    return convert(value, unit or key.unit, key.unit)


#: 「묶음을 가리지 않는다」 를 나타내는 표식. `None` 은 **이름 없는 묶음**이라 쓸 수 없다.
_EVERY: Any = object()


def _set_labels(db: Session, test_id: uuid.UUID) -> list[str | None]:
    """이 시험에 있는 조건 묶음들 — 이름 없는 것이 먼저.

    **한 벌뿐이면 묶음 이야기를 안 꺼낸다**(빈 목록이 아니라 `[None]` 하나다). 조건이
    한 벌인 시험이 대부분이고, 거기에 「묶음: 기본」 이 서면 없는 개념이 하나 는다.
    """
    rows = db.scalars(
        select(AttributeValue.set_label)
        .join(AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id)
        .where(
            AttributeValue.reliability_test_id == test_id,
            AttributeDefinition.kind == "condition",
            AttributeValue.is_current.is_(True),
        )
        .distinct()
    ).all()
    found = {one or None for one in rows}
    ordered = sorted((one for one in found if one), key=str)
    return ([None] if None in found else []) + ordered


def _conditions(
    db: Session, test_id: uuid.UUID, *, set_label: str | None = _EVERY
) -> tuple[list[ConditionQuery], list[SkippedConditionOut]]:
    """조건 속성 → 검색 조건. 범위는 두 물음으로 갈라진다.

    `set_label` 을 주면 **그 묶음만** 본다. 안 주면 묶음을 가리지 않고 전부 — 그것은 「이
    시험을 통째로(예외 경로까지) 돌릴 장비」 라는 다른 물음이다.
    """
    rows = db.execute(
        select(AttributeValue, AttributeDefinition, ConditionKey)
        .join(AttributeDefinition, AttributeValue.definition_id == AttributeDefinition.id)
        .join(ConditionKey, AttributeDefinition.condition_key_id == ConditionKey.id)
        .where(
            AttributeValue.reliability_test_id == test_id,
            AttributeDefinition.kind == "condition",
            # **지금 값만 판정에 실린다.** 과거 판의 조건까지 걸면 아무도 요구하지 않는
            # 조건이 만들어지고, 그 조건으로 장비가 걸러진다(0046).
            AttributeValue.is_current.is_(True),
        )
        .order_by(AttributeDefinition.sort_order, AttributeDefinition.label)
    ).all()
    if set_label is not _EVERY:
        rows = [one for one in rows if (one[0].set_label or None) == set_label]

    queries: list[ConditionQuery] = []
    skipped: list[SkippedConditionOut] = []
    for value, definition, key in rows:
        unit = value.unit or definition.unit
        low = _axis(value.num_min, unit, key)
        high = _axis(value.num_max, unit, key)
        point = _axis(value.num_value, unit, key)
        wrote = any(one is not None for one in (value.num_min, value.num_max, value.num_value))
        if not wrote:
            # 값이 안 적힌 조건은 「제한 없음」 이다. 물을 것이 없다.
            continue
        if low is None and high is None and point is None:
            skipped.append(
                SkippedConditionOut(
                    label=definition.label,
                    reason=f"단위 {unit}에서 {key.label} 단위({key.unit})로 변환 불가.",
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

    **조건이 한 벌이 아니면 묶음마다 따로 답한다**(`sets`). 주 조건 80 °C 와 「불량 시」
    70 °C 를 한 묶음으로 섞어 물으면, 실제로는 아무도 요구하지 않는 조건이 만들어진다 —
    그 조건으로 장비가 걸러지는데 왜 걸러졌는지 화면 어디에도 안 나온다.

    `items` 는 **모든 묶음을 한꺼번에** 만족하는 장비다. 그것도 답이다(예외 경로까지 이
    시험을 통째로 돌릴 장비), 다만 **유일한 답이 아니었던 것이 문제였다.** 묶음이 한
    벌뿐이면 `sets` 는 비어 있다 — 같은 표를 두 번 그릴 이유가 없다.

    묶음 **안의** 차례(프로파일 1·2·3·4)는 따로 안 가른다. 한 벌을 도는 동안 챔버는 그
    점들을 **다** 내야 하므로, 차례들을 한꺼번에 묻는 것이 곧 구간 전체를 묻는 것이다.

    부서로 좁히지 않는다 — 이 시스템의 물음은 부서를 가로지르고(옆 부서에 있으면 빌리러
    간다), 어느 부서 것인지는 줄마다 적혀 있다. 대신 **그 시험을 등록한 부서의 장비가
    위로 오게** 두지도 않는다: 순서는 검색과 같은 규칙(확실한 것이 위)이라야 두 화면이
    같은 답으로 읽힌다.
    """
    items = db.execute(
        select(ReliabilityTestItem.test_item_term_id, VocabularyTerm.value)
        .join(VocabularyTerm, ReliabilityTestItem.test_item_term_id == VocabularyTerm.id)
        .where(ReliabilityTestItem.reliability_test_id == test.id)
        .order_by(VocabularyTerm.value)
    ).all()

    def answer(conditions: list[ConditionQuery]) -> list[CapabilityItemOut]:
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
        return out

    every, skipped = _conditions(db, test.id)
    labels = _set_labels(db, test.id)
    sets: list[CapabilitySetOut] = []
    # **묶음이 둘 이상일 때만 따로 답한다.** 한 벌뿐이면 묶음별 답이 합친 답과 같은 것이라,
    # 똑같은 표를 두 번 그리는 셈이 된다.
    if len(labels) > 1:
        for label in labels:
            picked, dropped = _conditions(db, test.id, set_label=label)
            sets.append(
                CapabilitySetOut(
                    set_label=label,
                    conditions_asked=len(picked),
                    skipped=dropped,
                    items=answer(picked),
                )
            )
    return CapabilityOut(
        test_id=test.id,
        conditions_asked=len(every),
        skipped=skipped,
        items=answer(every),
        sets=sets,
    )


def preview(
    db: Session,
    user: User,
    *,
    test_item_term_ids: list[uuid.UUID],
    items: list[AttributeValueIn],
) -> CapabilityOut:
    """**아직 저장하지 않은 조건**으로 장비를 본다 — 적으면서 보는 자리.

    지금은 저장한 뒤 따로 열어야 보인다. 그래서 「95 °C 로 올리면 돌릴 장비가 0대」 를
    저장하고 나서 안다 — 돌릴 수 없는 조건을 적어 둔 시험이 그렇게 생긴다.

    **단위 환산은 서버가 한다.** 화면이 축 단위로 바꿔 보내게 하면 그 환산이 두 벌이 되고,
    두 벌은 갈라진다(`_conditions` 와 같은 길을 쓴다).
    """
    queries: list[ConditionQuery] = []
    skipped: list[SkippedConditionOut] = []
    for item in items:
        if item.definition_id is None:
            continue
        definition = db.get(AttributeDefinition, item.definition_id)
        if definition is None or definition.kind != "condition":
            continue
        if definition.condition_key_id is None:
            continue
        key = db.get(ConditionKey, definition.condition_key_id)
        if key is None:
            continue
        unit = item.unit or definition.unit
        low, high = _axis(item.num_min, unit, key), _axis(item.num_max, unit, key)
        point = _axis(item.num_value, unit, key)
        wrote = any(one is not None for one in (item.num_min, item.num_max, item.num_value))
        if not wrote:
            continue
        if low is None and high is None and point is None:
            skipped.append(
                SkippedConditionOut(
                    label=definition.label,
                    reason=f"단위 {unit}에서 {key.label} 단위({key.unit})로 변환 불가.",
                )
            )
            continue
        if point is not None:
            queries.append(ConditionQuery(condition_key_id=key.id, at=point))
        if high is not None:
            queries.append(ConditionQuery(condition_key_id=key.id, at_least=high))
        if low is not None:
            queries.append(ConditionQuery(condition_key_id=key.id, at_most=low))

    names = {
        one.id: one.value
        for one in db.scalars(
            select(VocabularyTerm).where(VocabularyTerm.id.in_(test_item_term_ids))
        )
    }
    out: list[CapabilityItemOut] = []
    for term_id in test_item_term_ids:
        found = search_services.search(
            db, user, SearchRequest(test_item_term_id=term_id, conditions=queries)
        )
        out.append(
            CapabilityItemOut(
                term_id=term_id,
                value=names.get(term_id, "(없는 항목)"),
                total=found.total,
                unmet_count=found.unmet_count,
                hits=found.hits[:MAX_HITS_PER_ITEM],
            )
        )
    return CapabilityOut(
        test_id=uuid.UUID(int=0),
        conditions_asked=len(queries),
        skipped=skipped,
        items=out,
        sets=[],
    )
