"""카탈로그 검색 — **「이 시험을 하려면 어떤 기종이 되나 / 사야 하나」.**

장비 검색(`services.search`)은 우리가 가진 것을 답한다. 가진 것이 없을 때 다음 물음은 늘
「그러면 무엇을 사나」 이고, 그 답은 카탈로그에 있다 — 계열 265 의 시험 항목 607 건과 기종
891 의 사양은 지금까지 검색에 안 걸렸다.

## 판정은 장비 검색과 같은 규칙, 같은 코드로

기종의 조건은 **장비를 만들 때 복사되는 것과 같은 계산**으로 뽑는다 — 계열 조건은 봉투,
기종 사양이 이긴다(`conditions_from_specs`). 판정(`met · accessory · unmet · unknown`)도
장비 검색의 `_verdict` 그대로다. 두 검색이 다른 규칙을 쓰면 「카탈로그에서는 되는데 등록하니
안 된다」 가 생기고, 그때 사람은 둘 다 안 믿는다.

## 기종 단위로 답한다

계열로 답하면 0.5~600 kN 봉투가 「300 kN 됨」 이 된다(ADR 0006). 조건에 안 맞는 기종은
빼고, 하나도 안 남은 계열은 안 온다.

## 이미 가진 것을 말한다

기종마다 **보유 대수**를 단다. 이미 있는 것을 또 사는 것이 이 시스템이 막으려는 일 중
하나이고, 그 숫자가 없으면 카탈로그 검색은 구매 목록일 뿐이다.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment, EquipmentModel, EquipmentSeries
from app.modules.equipment.specs import conditions_from_specs_bulk
from app.modules.methods.models import TestMethod
from app.modules.properties.services import test_item_ids_for_property
from app.modules.search.schemas import (
    CatalogHit,
    CatalogModelHit,
    CatalogSearchResponse,
    ConditionMatch,
    SearchRequest,
)
from app.modules.search.services import _asked, _hit_verdict, _judge, _range_text
from app.modules.test_items.models import (
    SeriesTestCondition,
    SeriesTestItem,
    SeriesTestItemMethod,
)
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared.permissions import visible_equipment_ids

#: 계열 상한. 넘으면 사람이 안 읽는다.
MAX_SERIES = 100


@dataclass(frozen=True)
class Bound:
    """조건 한 칸 — 장비 조건과 같은 모양이라 같은 판정 함수를 탄다."""

    min_value: float | None
    max_value: float | None
    text_value: str | None
    requires_accessory: bool


def _candidates(db: Session, request: SearchRequest) -> list[SeriesTestItem]:
    stmt = (
        select(SeriesTestItem)
        .join(EquipmentSeries, EquipmentSeries.id == SeriesTestItem.series_id)
        .where(EquipmentSeries.deleted_at.is_(None), EquipmentSeries.kind == "main")
    )
    if request.test_item_term_id:
        stmt = stmt.where(SeriesTestItem.test_item_term_id == request.test_item_term_id)
    elif request.property_term_id:
        stmt = stmt.where(
            SeriesTestItem.test_item_term_id.in_(
                test_item_ids_for_property(db, request.property_term_id)
            )
        )
    if request.method_id:
        # 규격을 걸어 둔 시험 항목만 — 카탈로그는 「이 규격을 지원한다」 를 계열마다 적어
        # 오므로 장비 검색과 달리 규격 없는 줄을 남기지 않는다.
        cited = select(SeriesTestItemMethod.series_test_item_id).where(
            SeriesTestItemMethod.method_id == request.method_id
        )
        stmt = stmt.where(
            (SeriesTestItem.method_id == request.method_id) | (SeriesTestItem.id.in_(cited))
        )
    return list(db.scalars(stmt))


def search_catalog(db: Session, user: User, request: SearchRequest) -> CatalogSearchResponse:
    items = _candidates(db, request)
    if not items:
        return CatalogSearchResponse(
            hits=[],
            total_series=0,
            total_models=0,
            unmet_models=0,
            expanded_test_items=_expanded(db, request),
        )

    series_ids = {one.series_id for one in items}
    series_by_id = {
        row.id: row
        for row in db.scalars(
            select(EquipmentSeries).where(EquipmentSeries.id.in_(series_ids))
        )
    }
    models_by_series: dict[uuid.UUID, list[EquipmentModel]] = defaultdict(list)
    for model in db.scalars(
        select(EquipmentModel)
        .where(EquipmentModel.series_id.in_(series_ids), EquipmentModel.deleted_at.is_(None))
        .order_by(EquipmentModel.name)
    ):
        models_by_series[model.series_id].append(model)
    all_models = [m for rows in models_by_series.values() for m in rows]

    keys = {
        key.id: key
        for key in db.scalars(
            select(ConditionKey).where(
                ConditionKey.id.in_([one.condition_key_id for one in request.conditions])
            )
        )
    }
    derived = conditions_from_specs_bulk(db, [m.id for m in all_models])
    series_limits: dict[uuid.UUID, dict[uuid.UUID, Bound]] = defaultdict(dict)
    for limit in db.scalars(
        select(SeriesTestCondition).where(
            SeriesTestCondition.series_test_item_id.in_([one.id for one in items])
        )
    ):
        series_limits[limit.series_test_item_id][limit.condition_key_id] = Bound(
            limit.min_value, limit.max_value, limit.text_value, limit.requires_accessory
        )

    # 보유 대수 — 내가 볼 수 있는 장비만. 남의 부서가 가린 것은 안 센다.
    owned: dict[uuid.UUID, int] = {
        model_id: count
        for model_id, count in db.execute(
            select(Equipment.model_id, func.count())
            .where(
                Equipment.id.in_(visible_equipment_ids(db, user)),
                Equipment.model_id.in_([m.id for m in all_models]),
            )
            .group_by(Equipment.model_id)
        ).all()
    }
    cited: dict[uuid.UUID, list[str]] = defaultdict(list)
    for item_id, code in db.execute(
        select(SeriesTestItemMethod.series_test_item_id, TestMethod.code)
        .join(TestMethod, TestMethod.id == SeriesTestItemMethod.method_id)
        .where(SeriesTestItemMethod.series_test_item_id.in_([one.id for one in items]))
        .order_by(TestMethod.code)
    ).all():
        cited[item_id].append(code)
    # 시험 항목 자체가 규격을 하나 가리키기도 한다(`method_id`) — 인용 표와 따로.
    direct = {
        row.id: row.code
        for row in db.scalars(
            select(TestMethod).where(
                TestMethod.id.in_({one.method_id for one in items if one.method_id})
            )
        )
    }
    for item in items:
        if item.method_id and direct.get(item.method_id) not in cited[item.id]:
            cited[item.id].insert(0, direct[item.method_id])
    term_values = {
        row.id: row.value
        for row in db.scalars(
            select(VocabularyTerm).where(
                VocabularyTerm.id.in_(
                    {one.test_item_term_id for one in items}
                    | {s.maker_term_id for s in series_by_id.values() if s.maker_term_id}
                    | {s.category_term_id for s in series_by_id.values() if s.category_term_id}
                )
            )
        )
    }

    hits: list[CatalogHit] = []
    unmet = 0
    for item in items:
        series = series_by_id.get(item.series_id)
        if series is None:
            continue
        models_out: list[CatalogModelHit] = []
        for model in models_by_series.get(series.id, []):
            limits: dict[uuid.UUID, Bound] = dict(series_limits.get(item.id, {}))
            # 기종 사양이 계열 봉투를 이긴다 — 장비를 만들 때와 같은 규칙.
            for key_id, (low, high, _label, accessory) in derived.get(model.id, {}).items():
                limits[key_id] = Bound(low, high, None, accessory)
            matches = []
            for query in request.conditions:
                key = keys.get(query.condition_key_id)
                if key is None:
                    continue
                verdict_one, reason = _judge(query, limits.get(key.id))
                matches.append(
                    ConditionMatch(
                        condition_key_id=key.id,
                        condition_label=key.label,
                        display_unit=key.display_unit or key.si_unit,
                        verdict=verdict_one,
                        asked=_asked(query, key),
                        condition_range=_range_text(limits.get(key.id), key),
                        reason=reason,
                    )
                )
            verdict = _hit_verdict(matches)
            if verdict is None:
                unmet += 1
                continue
            models_out.append(
                CatalogModelHit(
                    model_id=model.id,
                    model_name=model.name,
                    verdict=verdict,
                    conditions=matches,
                    owned_units=owned.get(model.id, 0),
                )
            )
        if not models_out:
            continue
        hits.append(
            CatalogHit(
                series_id=series.id,
                series_name=series.name,
                maker=term_values.get(series.maker_term_id) if series.maker_term_id else None,
                category=(
                    term_values.get(series.category_term_id)
                    if series.category_term_id
                    else None
                ),
                test_item=term_values.get(item.test_item_term_id, ""),
                methods=cited.get(item.id, []),
                note=item.note,
                models=models_out,
            )
        )

    # 가진 것이 있는 계열이 위로 — 사기 전에 있는 것을 본다. 그다음은 이름. **늘 결정적이다.**
    hits.sort(
        key=lambda hit: (
            -sum(m.owned_units for m in hit.models),
            _best_rank(hit),
            hit.series_name,
        )
    )
    return CatalogSearchResponse(
        hits=hits[:MAX_SERIES],
        # 한 계열이 시험 항목마다 한 장이라 장 수와 계열 수가 다르다 — 사람이 세는 것은
        # 계열이다.
        total_series=len({hit.series_id for hit in hits}),
        total_models=sum(len(hit.models) for hit in hits),
        unmet_models=unmet,
        expanded_test_items=_expanded(db, request),
    )


_RANK = {"match": 0, "accessory": 1, "partial": 2, "unknown": 3}


def _best_rank(hit: CatalogHit) -> int:
    return min((_RANK.get(m.verdict, 9) for m in hit.models), default=9)


def _expanded(db: Session, request: SearchRequest) -> list[str]:
    if not request.property_term_id or request.test_item_term_id:
        return []
    ids = test_item_ids_for_property(db, request.property_term_id)
    return sorted(db.scalars(select(VocabularyTerm.value).where(VocabularyTerm.id.in_(ids))))
