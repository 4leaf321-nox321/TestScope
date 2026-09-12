"""시험 항목 카탈로그 — **사슬의 가운데에서 출발하는 눈.**

    물성  ⇄  시험 항목  →  규격(요구 조건)  →  계열/기종  →  보유 장비

카탈로그의 네 화면(계열·기종·규격·물성)이 전부 「→ 시험 항목」 으로 향하는데, 시험 항목에서
출발하는 화면이 없었다. 「인장」 하나를 두고 얻는 물성 5 · 규격 12 · 되는 계열 42 · 보유 7대
를 한 눈에 보는 자리 — 그리고 0 이 곧 공백인 자리.

## 한 번에 센다

96 줄에 다섯 수를 달려고 줄마다 다섯 번 물으면 480 회다. 각 수를 GROUP BY 한 번으로
받아 사전으로 든다.

## 보유 장비는 내가 볼 수 있는 것만

남의 부서가 가린 장비를 세면 「우리 조직에 있다」 가 되고, 그 사람은 그 장비를 못 쓴다.
검색과 같은 규칙(`visible_equipment_ids`).
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment, EquipmentModel, EquipmentSeries
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.properties.models import TestItemProperty
from app.modules.test_items.models import (
    EquipmentTestItem,
    SeriesTestItem,
    SeriesTestItemMethod,
    TestItemConditionKey,
)
from app.modules.test_items.schemas import (
    TestItemCatalogOut,
    TestItemCatalogRow,
    TestItemConditionKeyOut,
    TestItemEquipmentOut,
    TestItemMethodOut,
    TestItemPropertyLinkOut,
    TestItemSeriesOut,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.workspaces.models import Workspace
from app.shared.errors import NotFound
from app.shared.permissions import visible_equipment_ids


def _terms(db: Session) -> list[VocabularyTerm]:
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    if axis is None:
        return []
    return list(
        db.scalars(
            select(VocabularyTerm)
            .where(VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.status == "active")
            .order_by(VocabularyTerm.value)
        )
    )


def _counts(db: Session, user: User) -> dict[str, dict[uuid.UUID, int]]:
    """시험 항목마다의 수들 — 각각 질의 한 번."""
    out: dict[str, dict[uuid.UUID, int]] = defaultdict(dict)
    for term_id, count in db.execute(
        select(TestItemProperty.test_item_term_id, func.count()).group_by(
            TestItemProperty.test_item_term_id
        )
    ).all():
        out["properties_total"][term_id] = int(count)
    for term_id, count in db.execute(
        select(TestItemProperty.test_item_term_id, func.count())
        .where(TestItemProperty.status == "confirmed")
        .group_by(TestItemProperty.test_item_term_id)
    ).all():
        out["properties_confirmed"][term_id] = int(count)
    for term_id, count in db.execute(
        select(TestMethod.test_item_term_id, func.count())
        .where(TestMethod.deleted_at.is_(None), TestMethod.test_item_term_id.is_not(None))
        .group_by(TestMethod.test_item_term_id)
    ).all():
        out["methods_total"][term_id] = int(count)
    for term_id, count in db.execute(
        select(TestMethod.test_item_term_id, func.count(func.distinct(TestMethod.id)))
        .join(MethodRequirement, MethodRequirement.method_id == TestMethod.id)
        .where(TestMethod.deleted_at.is_(None), TestMethod.test_item_term_id.is_not(None))
        .group_by(TestMethod.test_item_term_id)
    ).all():
        out["methods_with_requirements"][term_id] = int(count)
    live_series = select(EquipmentSeries.id).where(
        EquipmentSeries.deleted_at.is_(None), EquipmentSeries.kind == "main"
    )
    for term_id, count in db.execute(
        select(
            SeriesTestItem.test_item_term_id,
            func.count(func.distinct(SeriesTestItem.series_id)),
        )
        .where(SeriesTestItem.series_id.in_(live_series))
        .group_by(SeriesTestItem.test_item_term_id)
    ).all():
        out["series_count"][term_id] = int(count)
    for term_id, count in db.execute(
        select(SeriesTestItem.test_item_term_id, func.count(func.distinct(EquipmentModel.id)))
        .join(EquipmentModel, EquipmentModel.series_id == SeriesTestItem.series_id)
        .where(EquipmentModel.deleted_at.is_(None), SeriesTestItem.series_id.in_(live_series))
        .group_by(SeriesTestItem.test_item_term_id)
    ).all():
        out["model_count"][term_id] = int(count)
    for term_id, count in db.execute(
        select(
            EquipmentTestItem.test_item_term_id,
            func.count(func.distinct(EquipmentTestItem.equipment_id)),
        )
        .where(EquipmentTestItem.equipment_id.in_(visible_equipment_ids(db, user)))
        .group_by(EquipmentTestItem.test_item_term_id)
    ).all():
        out["equipment_count"][term_id] = int(count)
    return out


def _aliases(db: Session, term_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    out: dict[uuid.UUID, list[str]] = defaultdict(list)
    for term_id, alias in db.execute(
        select(VocabularyAlias.term_id, VocabularyAlias.value)
        .where(VocabularyAlias.term_id.in_(term_ids), VocabularyAlias.is_active.is_(True))
        .order_by(VocabularyAlias.value)
    ).all():
        out[term_id].append(alias)
    return out


def _axes(db: Session, term_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ConditionKey]]:
    out: dict[uuid.UUID, list[ConditionKey]] = defaultdict(list)
    for term_id, key in db.execute(
        select(TestItemConditionKey.test_item_term_id, ConditionKey)
        .join(ConditionKey, ConditionKey.id == TestItemConditionKey.condition_key_id)
        .where(TestItemConditionKey.test_item_term_id.in_(term_ids))
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all():
        out[term_id].append(key)
    return out


def list_rows(db: Session, user: User) -> list[TestItemCatalogRow]:
    terms = _terms(db)
    ids = [t.id for t in terms]
    counts = _counts(db, user)
    aliases = _aliases(db, ids)
    axes = _axes(db, ids)
    return [
        TestItemCatalogRow(
            id=t.id,
            value=t.value,
            code=t.code,
            aliases=aliases.get(t.id, []),
            properties_total=counts["properties_total"].get(t.id, 0),
            properties_confirmed=counts["properties_confirmed"].get(t.id, 0),
            methods_total=counts["methods_total"].get(t.id, 0),
            methods_with_requirements=counts["methods_with_requirements"].get(t.id, 0),
            series_count=counts["series_count"].get(t.id, 0),
            model_count=counts["model_count"].get(t.id, 0),
            equipment_count=counts["equipment_count"].get(t.id, 0),
            condition_keys=[k.label for k in axes.get(t.id, [])],
            condition_key_ids=[k.id for k in axes.get(t.id, [])],
        )
        for t in terms
    ]


def get_term(db: Session, term_id: uuid.UUID) -> VocabularyTerm:
    term = db.get(VocabularyTerm, term_id)
    axis = db.get(Vocabulary, term.vocabulary_id) if term else None
    if term is None or axis is None or axis.slug != "test_item":
        raise NotFound("TSC-TESTITEM-0010", "시험 항목을 찾을 수 없습니다.")
    return term


def detail(db: Session, user: User, term_id: uuid.UUID) -> TestItemCatalogOut:
    term = get_term(db, term_id)

    props = [
        TestItemPropertyLinkOut(
            link_id=link.id,
            property_term_id=prop.id,
            property=prop.value,
            property_code=prop.code,
            status=link.status,
        )
        for link, prop in db.execute(
            select(TestItemProperty, VocabularyTerm)
            .join(VocabularyTerm, VocabularyTerm.id == TestItemProperty.property_term_id)
            .where(TestItemProperty.test_item_term_id == term.id)
            .order_by(VocabularyTerm.value)
        ).all()
    ]

    with_req = set(db.scalars(select(MethodRequirement.method_id).distinct()))
    series_per_method: dict[uuid.UUID, int] = {
        method_id: int(count)
        for method_id, count in db.execute(
            select(
                SeriesTestItemMethod.method_id,
                func.count(func.distinct(SeriesTestItem.series_id)),
            )
            .join(
                SeriesTestItem, SeriesTestItem.id == SeriesTestItemMethod.series_test_item_id
            )
            .group_by(SeriesTestItemMethod.method_id)
        ).all()
    }
    methods = [
        TestItemMethodOut(
            id=m.id,
            code=m.code,
            edition=m.edition,
            title=m.title,
            has_requirements=m.id in with_req,
            series_count=series_per_method.get(m.id, 0),
        )
        for m in db.scalars(
            select(TestMethod)
            .where(TestMethod.test_item_term_id == term.id, TestMethod.deleted_at.is_(None))
            .order_by(TestMethod.code, TestMethod.edition)
        )
    ]

    rows = db.execute(
        select(SeriesTestItem, EquipmentSeries)
        .join(EquipmentSeries, EquipmentSeries.id == SeriesTestItem.series_id)
        .where(
            SeriesTestItem.test_item_term_id == term.id,
            EquipmentSeries.deleted_at.is_(None),
            EquipmentSeries.kind == "main",
        )
        .order_by(EquipmentSeries.name)
    ).all()
    series_ids = [s.id for _, s in rows]
    model_counts = {
        sid: int(count)
        for sid, count in db.execute(
            select(EquipmentModel.series_id, func.count())
            .where(
                EquipmentModel.series_id.in_(series_ids), EquipmentModel.deleted_at.is_(None)
            )
            .group_by(EquipmentModel.series_id)
        ).all()
    }
    codes: dict[uuid.UUID, list[str]] = defaultdict(list)
    for item_id, code in db.execute(
        select(SeriesTestItemMethod.series_test_item_id, TestMethod.code)
        .join(TestMethod, TestMethod.id == SeriesTestItemMethod.method_id)
        .where(SeriesTestItemMethod.series_test_item_id.in_([r.id for r, _ in rows]))
        .order_by(TestMethod.code)
    ).all():
        codes[item_id].append(code)
    # 시험 항목 자체가 규격 하나를 가리키기도 한다(`method_id`) — 인용 표와 따로.
    direct = {
        m.id: m.code
        for m in db.scalars(
            select(TestMethod).where(
                TestMethod.id.in_({item.method_id for item, _ in rows if item.method_id})
            )
        )
    }
    for item, _ in rows:
        if item.method_id and direct.get(item.method_id) not in codes[item.id]:
            codes[item.id].insert(0, direct[item.method_id])
    term_ids = {s.maker_term_id for _, s in rows if s.maker_term_id} | {
        s.category_term_id for _, s in rows if s.category_term_id
    }
    names = {
        t.id: t.value
        for t in db.scalars(select(VocabularyTerm).where(VocabularyTerm.id.in_(term_ids)))
    }
    series = [
        TestItemSeriesOut(
            id=s.id,
            name=s.name,
            maker=names.get(s.maker_term_id) if s.maker_term_id else None,
            category=names.get(s.category_term_id) if s.category_term_id else None,
            model_count=model_counts.get(s.id, 0),
            method_codes=codes.get(item.id, []),
        )
        for item, s in rows
    ]

    workspaces = {w.id: w.name for w in db.scalars(select(Workspace))}
    equipment = [
        TestItemEquipmentOut(
            id=e.id,
            asset_no=e.asset_no,
            name=e.name,
            workspace=workspaces.get(e.owner_workspace_id),
            status=e.status,
        )
        for e in db.scalars(
            select(Equipment)
            .join(EquipmentTestItem, EquipmentTestItem.equipment_id == Equipment.id)
            .where(
                EquipmentTestItem.test_item_term_id == term.id,
                Equipment.id.in_(visible_equipment_ids(db, user)),
            )
            .distinct()
            .order_by(Equipment.asset_no)
        )
    ]

    axes = _axes(db, [term.id]).get(term.id, [])
    return TestItemCatalogOut(
        id=term.id,
        value=term.value,
        code=term.code,
        aliases=_aliases(db, [term.id]).get(term.id, []),
        properties=props,
        methods=methods,
        series=series,
        equipment=equipment,
        condition_keys=[
            TestItemConditionKeyOut(
                id=k.id, key=k.key, label=k.label, unit=k.display_unit or k.si_unit
            )
            for k in axes
        ],
        can_edit=user.is_system_admin,
    )


def set_condition_keys(
    db: Session, term_id: uuid.UUID, condition_key_ids: list[uuid.UUID]
) -> None:
    """검색축을 **통째로 바꾼다** — 목록 편집은 전체를 보내는 편이 어긋날 곳이 없다."""
    term = get_term(db, term_id)
    wanted = set(condition_key_ids)
    known = set(db.scalars(select(ConditionKey.id).where(ConditionKey.id.in_(wanted))))
    missing = wanted - known
    if missing:
        raise NotFound("TSC-TESTITEM-0011", "조건 정의를 찾을 수 없습니다.")
    for row in db.scalars(
        select(TestItemConditionKey).where(TestItemConditionKey.test_item_term_id == term.id)
    ):
        if row.condition_key_id in wanted:
            wanted.discard(row.condition_key_id)
        else:
            db.delete(row)
    for key_id in wanted:
        db.add(TestItemConditionKey(test_item_term_id=term.id, condition_key_id=key_id))
    db.commit()
