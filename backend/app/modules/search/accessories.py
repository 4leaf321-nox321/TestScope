"""**부속을 붙이면 되나.** 본체만으로 안 되는 조건에 챔버·노가 답한다.

만능시험기는 상온에서만 돈다. 「300 °C 에서 인장」 을 물으면 본체 사양으로는 `unknown`
(온도를 안 적었다) 이거나 `unmet`(상온까지다) 이고, 지금까지 검색은 거기서 멈췄다. 그런데
실무의 답은 대개 **「노를 달면 된다」** 이고, 그 노는 이미 카탈로그에 계열로 있고 본체와
관계(`SeriesRelation`)로 이어져 있다 — 실측(2026-09-21)으로 그렇게 답이 생기는 본체 계열이
19개, 그중 13개는 지금 `unknown` 으로만 답한다.

## 아무 부속이나 온도를 대지 않는다

그립의 사양표에도 `-130 ~ 315 °C` 가 적혀 있다. 그것은 **그 그립이 견디는 온도**지 그립을
달면 그 온도가 나온다는 말이 아니다. 신율계도 같다. 그래서 **분류마다 무엇을 댈 수 있는지**
를 표(`SUPPLIES`)로 못 박는다 — 항온조는 온도·습도, 노는 온도. 챔버 사양의 「하중 용량」 은
거꾸로 **제약**이라 여기서 대지 않는다.

## 어느 쪽에서 이어도 같은 관계다

카탈로그가 사람 손으로 자라서 `본체 -> 챔버`(`compatible_accessory`)와
`챔버 -> 본체`(`fits_on`)가 섞여 있다. 한쪽만 보면 같은 짝이 어느 객체에서 들어왔느냐로
답이 갈린다 — **양쪽 다 본다.**

## 기종 하나를 짚어 답한다

계열 봉투로 답하면 「-70~300 °C 챔버 계열」 이 600 °C 도 된다고 말한다(ADR 0006). 물은
조건을 실제로 만족하는 **기종**을 골라, 그 이름과 범위와 **우리가 그것을 몇 대 갖고 있는지**
까지 답한다. 이미 있는 챔버를 또 사는 것이 이 시스템이 막으려는 일이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    SeriesRelation,
)
from app.modules.equipment.specs import conditions_from_specs_bulk
from app.modules.search.schemas import AccessoryOffer, ConditionMatch, ConditionQuery
from app.modules.search.verdict import Bound, _judge, _range_text
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared.permissions import visible_equipment_ids

#: 이 분류의 부속이 **댈 수 있는 조건 축**(`ConditionKey.key`). 여기 없는 짝은 안 댄다 —
#: 그립의 내열 온도는 그립이 견디는 값이지 시험 온도가 아니다.
SUPPLIES: dict[str, frozenset[str]] = {
    "environmental_chamber": frozenset({"temperature", "humidity"}),
    "furnace": frozenset({"temperature"}),
}

#: 「달 수 있다」 를 뜻하는 관계. 방향은 양쪽 다 본다. `extends_capability`(굽힘 지그
#: 따위)는 **시험 항목**을 늘리는 것이라 조건을 대지 않는다.
ATTACH = ("extends_temperature", "compatible_accessory", "fits_on")

#: 같은 짝이 관계 여럿으로 이어져 있을 때 무엇을 적을지. 뜻이 분명한 것이 이긴다.
_ATTACH_RANK = {name: index for index, name in enumerate(ATTACH)}


class _Supplier:
    """조건을 댈 수 있는 부속 계열 한 줄 — 이름과 **댈 수 있는 축들.**"""

    __slots__ = ("axes", "name")

    def __init__(self, name: str, axes: frozenset[str]) -> None:
        self.name = name
        self.axes = axes


def offers_for(
    db: Session,
    user: User,
    series_ids: Iterable[uuid.UUID],
    queries: list[ConditionQuery],
    keys: Mapping[uuid.UUID, ConditionKey],
) -> dict[tuple[uuid.UUID, uuid.UUID], AccessoryOffer]:
    """{(본체 계열 id, 조건 id): 그 조건을 대 주는 부속}.

    **한 번에 읽는다** — 계열마다 관계를 캐면 검색 한 번에 수백 번 왕복한다.
    """
    hosts = set(series_ids)
    axes = frozenset().union(*SUPPLIES.values())
    asked = [
        query
        for query in queries
        if (key := keys.get(query.condition_key_id)) is not None and key.key in axes
    ]
    if not hosts or not asked:
        return {}

    attached = _attached(db, hosts)
    suppliers = _suppliers(db, {part for pairs in attached.values() for part, _ in pairs})
    if not suppliers:
        return {}

    models_by_series: dict[uuid.UUID, list[EquipmentModel]] = {}
    for model in db.scalars(
        select(EquipmentModel).where(
            EquipmentModel.series_id.in_(suppliers),
            EquipmentModel.deleted_at.is_(None),
        )
    ):
        models_by_series.setdefault(model.series_id, []).append(model)
    model_ids = [model.id for rows in models_by_series.values() for model in rows]
    bounds = conditions_from_specs_bulk(db, model_ids)
    owned = _owned_units(db, user, model_ids)

    out: dict[tuple[uuid.UUID, uuid.UUID], AccessoryOffer] = {}
    for host, pairs in attached.items():
        for query in asked:
            key = keys[query.condition_key_id]
            best: tuple[tuple[int, str, str], AccessoryOffer] | None = None
            for part, relation in pairs:
                supplier = suppliers.get(part)
                if supplier is None or key.key not in supplier.axes:
                    continue
                for model in models_by_series.get(part, []):
                    low, high, _label, needs = bounds.get(model.id, {}).get(
                        key.id, (None, None, "", False)
                    )
                    if low is None and high is None:
                        continue
                    bound = Bound(low, high, None, bool(needs))
                    if _judge(query, bound)[0] != "met":
                        continue
                    units = owned.get(model.id, 0)
                    # 갖고 있는 것이 먼저, 그다음은 이름 — **늘 결정적이다.**
                    rank = (-units, supplier.name, model.name)
                    if best is not None and rank >= best[0]:
                        continue
                    best = (
                        rank,
                        AccessoryOffer(
                            series_id=part,
                            series_name=supplier.name,
                            model_id=model.id,
                            model_name=model.name,
                            condition_range=_range_text(bound, key) or "",
                            owned_units=units,
                            relation=relation,
                        ),
                    )
            if best is not None:
                out[(host, query.condition_key_id)] = best[1]
    return out


def fill(
    matches: list[ConditionMatch],
    offers: Mapping[tuple[uuid.UUID, uuid.UUID], AccessoryOffer],
    series_id: uuid.UUID | None,
) -> list[ConditionMatch]:
    """본체가 못 대는 조건에 부속이 답하면 그 칸을 `accessory` 로 바꾼다.

    **`unmet` 도 바꾼다.** 상온까지인 시험기에 노를 달면 되는 것이 실무의 답인데, 지금은
    그 줄이 결과에서 통째로 빠진다(`_hit_verdict`) — 빠지면 사람은 「그런 장비가 없다」 로
    읽고 전화를 돌린다. 이미 `met`·`accessory` 인 칸은 손대지 않는다: 본체로 되는 것을
    부속이 있어야 되는 것으로 낮출 이유가 없다.
    """
    if series_id is None or not offers:
        return matches
    for one in matches:
        if one.verdict in ("met", "accessory"):
            continue
        offer = offers.get((series_id, one.condition_key_id))
        if offer is None:
            continue
        one.verdict = "accessory"
        one.reason = None
        one.accessory = offer
    return matches


def _attached(
    db: Session, hosts: set[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[uuid.UUID, str]]]:
    """{본체 계열: [(부속 계열, 관계)]}. **관계를 양쪽 방향으로 읽는다.**"""
    rows = db.execute(
        select(
            SeriesRelation.host_series_id,
            SeriesRelation.part_series_id,
            SeriesRelation.relation,
        ).where(
            SeriesRelation.relation.in_(ATTACH),
            or_(
                SeriesRelation.host_series_id.in_(hosts),
                SeriesRelation.part_series_id.in_(hosts),
            ),
        )
    ).all()
    found: dict[uuid.UUID, dict[uuid.UUID, str]] = {}
    for host_id, part_id, relation in rows:
        for host, part in ((host_id, part_id), (part_id, host_id)):
            if host not in hosts or host == part:
                continue
            seen = found.setdefault(host, {})
            before = seen.get(part)
            if before is None or _ATTACH_RANK[relation] < _ATTACH_RANK[before]:
                seen[part] = relation
    return {
        host: sorted(pairs.items(), key=lambda one: str(one[0]))
        for host, pairs in found.items()
    }


def _suppliers(db: Session, series_ids: set[uuid.UUID]) -> dict[uuid.UUID, _Supplier]:
    """부속 계열 중 **조건을 댈 수 있는 분류**만. 그립·신율계는 여기서 빠진다."""
    if not series_ids:
        return {}
    rows = db.execute(
        select(EquipmentSeries.id, EquipmentSeries.name, VocabularyTerm.code)
        .join(VocabularyTerm, VocabularyTerm.id == EquipmentSeries.category_term_id)
        .where(
            EquipmentSeries.id.in_(series_ids),
            EquipmentSeries.deleted_at.is_(None),
            EquipmentSeries.kind.in_(("accessory", "sensor")),
            VocabularyTerm.code.in_(SUPPLIES),
        )
    ).all()
    return {row[0]: _Supplier(row[1], SUPPLIES[row[2]]) for row in rows}


def _owned_units(db: Session, user: User, model_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """이 부속 기종을 **우리가 몇 대 갖고 있나.** 내가 볼 수 있는 것만 — 남의 부서가
    가린 것을 세면 있지도 않은 챔버를 전제로 답하게 된다."""
    if not model_ids:
        return {}
    return {
        model_id: count
        for model_id, count in db.execute(
            select(Equipment.model_id, func.count())
            .where(
                Equipment.id.in_(visible_equipment_ids(db, user)),
                Equipment.model_id.in_(model_ids),
            )
            .group_by(Equipment.model_id)
        ).all()
    }
