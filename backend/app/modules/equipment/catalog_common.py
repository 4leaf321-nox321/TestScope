"""카탈로그의 공통 조각 — 계열·기종 하나 꺼내기, 계열의 시험 항목·관계 읽기,
목록을 쪽 단위로 묶는 셈, 거르기 선택지.

`catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.equipment.category_tree import rollup
from app.modules.equipment.models import (
    AVAILABLE_STATUSES,
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    SeriesRelation,
)
from app.modules.equipment.schemas import (
    CatalogFilterOptionsOut,
    CitedMethodOut,
    FilterOption,
    ModelLimitOut,
    SeriesRelationOut,
    SeriesTestItemOut,
)
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.test_items.models import (
    SeriesTestCondition,
    SeriesTestItem,
    SeriesTestItemMethod,
)
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared.errors import NotFound


def _term_value(db: Session, term_id: uuid.UUID | None) -> str | None:
    if term_id is None:
        return None
    term = db.get(VocabularyTerm, term_id)
    return term.value if term else None


def get_series(db: Session, series_id: uuid.UUID) -> EquipmentSeries:
    found = db.get(EquipmentSeries, series_id)
    if found is None or found.deleted_at is not None:
        raise NotFound("TSC-CATALOG-0009", "장비 계열을 찾을 수 없습니다.")
    return found


def get_model(db: Session, model_id: uuid.UUID) -> EquipmentModel:
    found = db.get(EquipmentModel, model_id)
    if found is None or found.deleted_at is not None:
        raise NotFound("TSC-CATALOG-0001", "장비 기종을 찾을 수 없습니다.")
    return found


# --- 계열의 시험 항목 ---------------------------------------------------------------


def _limits(db: Session, equipment_test_item_id: uuid.UUID) -> list[ModelLimitOut]:
    rows = db.execute(
        select(SeriesTestCondition, ConditionKey)
        .join(ConditionKey, ConditionKey.id == SeriesTestCondition.condition_key_id)
        .where(SeriesTestCondition.series_test_item_id == equipment_test_item_id)
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all()
    return [
        ModelLimitOut(
            id=limit.id,
            condition_key_id=key.id,
            condition_key=key.key,
            condition_label=key.label,
            si_unit=key.si_unit,
            display_unit=key.display_unit,
            min_value=limit.min_value,
            max_value=limit.max_value,
            text_value=limit.text_value,
            requires_accessory=limit.requires_accessory,
            note=limit.note,
        )
        for limit, key in rows
    ]


def _cited_methods(db: Session, equipment_test_item_id: uuid.UUID) -> list[CitedMethodOut]:
    """이 시험 항목이 인용하는 규격들.

    **요구 조건이 있는지 함께 말한다.** 조건이 없는 규격은 검색이 조건으로 좁히지
    못하는데, 화면이 그 사실을 말해 주지 않으면 아무도 채우지 않는다.
    """
    rows = db.execute(
        select(TestMethod)
        .join(SeriesTestItemMethod, SeriesTestItemMethod.method_id == TestMethod.id)
        .where(
            SeriesTestItemMethod.series_test_item_id == equipment_test_item_id,
            TestMethod.deleted_at.is_(None),
        )
        .order_by(TestMethod.code)
    ).scalars()
    out: list[CitedMethodOut] = []
    for row in rows:
        needs = (
            db.scalar(
                select(func.count())
                .select_from(MethodRequirement)
                .where(MethodRequirement.method_id == row.id)
            )
            or 0
        )
        out.append(
            CitedMethodOut(
                id=row.id,
                code=row.code,
                edition=row.edition,
                title=row.title,
                has_requirements=needs > 0,
            )
        )
    return out


def _test_items(db: Session, series_id: uuid.UUID) -> list[SeriesTestItemOut]:
    rows = db.scalars(
        select(SeriesTestItem)
        .where(SeriesTestItem.series_id == series_id)
        .order_by(SeriesTestItem.created_at)
    )
    out: list[SeriesTestItemOut] = []
    for row in rows:
        item = db.get(VocabularyTerm, row.test_item_term_id)
        method = db.get(TestMethod, row.method_id) if row.method_id else None
        out.append(
            SeriesTestItemOut(
                id=row.id,
                test_item_term_id=row.test_item_term_id,
                test_item=item.value if item else "",
                method_id=row.method_id,
                method_code=(
                    f"{method.code} {method.edition or ''}".strip() if method else None
                ),
                methods=_cited_methods(db, row.id),
                note=row.note,
                limits=_limits(db, row.id),
            )
        )
    return out


def _relations(db: Session, series_id: uuid.UUID) -> list[SeriesRelationOut]:
    """이 계열에 붙은 관계 — **양방향으로 본다.**

    한쪽만 보여 주면 챔버 화면이 늘 비어 있다. 「이 챔버가 붙는 시험기들」 은
    관계의 대상 쪽에서만 보이는 사실이다.
    """
    rows = db.scalars(
        select(SeriesRelation).where(
            or_(
                SeriesRelation.host_series_id == series_id,
                SeriesRelation.part_series_id == series_id,
            )
        )
    )
    out: list[SeriesRelationOut] = []
    for row in rows:
        inbound = row.part_series_id == series_id
        other_id = row.host_series_id if inbound else row.part_series_id
        other = db.get(EquipmentSeries, other_id)
        if other is None or other.deleted_at is not None:
            continue
        out.append(
            SeriesRelationOut(
                id=row.id,
                relation=row.relation,
                other_series_id=other.id,
                other_name=other.name,
                other_maker=_term_value(db, other.maker_term_id),
                other_kind=other.kind,
                note=row.note,
                inbound=inbound,
            )
        )
    return sorted(out, key=lambda one: (one.relation, one.other_name))


# --- 목록을 쪽 단위로 묶는 자리 -----------------------------------------------
#
# **줄마다 묻지 않는다.** 한 줄씩 채우면 50줄짜리 한 쪽이 질의를 1,058회 한다 —
# 재 보면 용어 425회, 시험 항목에 딸린 규격·조건이 379회, 보유 대수 50회다.
# 한 쪽에 드는 질의를 줄 수와 무관하게 만드는 것이 여기 있는 함수들의 일이다.
#
# 목록이 커져서 느린 것이 아니라 **한 줄이 비싼 것**이라, 쪽 넘김으로는 안 고쳐진다.


def _term_values(db: Session, term_ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    """용어 여럿을 한 번에. 제조사·분류·형태를 줄마다 꺼내면 그게 곧 425회다."""
    wanted = {one for one in term_ids if one is not None}
    if not wanted:
        return {}
    rows = db.execute(
        select(VocabularyTerm.id, VocabularyTerm.value).where(VocabularyTerm.id.in_(wanted))
    ).all()
    return {term_id: value for term_id, value in rows}


def _model_counts(db: Session, series_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """계열마다 기종이 몇 개인가."""
    if not series_ids:
        return {}
    rows = db.execute(
        select(EquipmentModel.series_id, func.count())
        .where(EquipmentModel.series_id.in_(series_ids), EquipmentModel.deleted_at.is_(None))
        .group_by(EquipmentModel.series_id)
    ).all()
    return {series_id: count for series_id, count in rows}


def _unit_counts(
    db: Session, column: Any, keys: list[uuid.UUID], joined: Any = None
) -> dict[uuid.UUID, tuple[int, int]]:
    """보유 대수와 가동 대수를 **세어서** 가져온다.

    전에는 장비 행을 통째로 읽어 파이썬에서 셌다. 대장이 커지면 그 방식은 한 계열의
    장비 수만큼 메모리를 쓰는데, 화면에 나가는 것은 숫자 둘이다.
    """
    if not keys:
        return {}
    stmt = select(
        column,
        func.count(),
        func.count().filter(Equipment.status.in_(AVAILABLE_STATUSES)),
    ).where(Equipment.deleted_at.is_(None))
    if joined is not None:
        stmt = stmt.join(joined, joined.id == Equipment.model_id)
    rows = db.execute(stmt.where(column.in_(keys)).group_by(column)).all()
    return {key: (total, working) for key, total, working in rows}


def _test_item_names(db: Session, series_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    """계열마다 시험 항목 **이름들**. 조건 수치와 인용 규격은 안 들고 온다.

    목록이 그것으로 하는 일은 이름 두엇을 적거나 개수를 세는 것뿐인데, 상세를 만드느라
    50줄에 질의 379회와 46 KB 를 썼다.
    """
    if not series_ids:
        return {}
    rows = db.execute(
        select(SeriesTestItem.series_id, VocabularyTerm.value)
        .join(VocabularyTerm, VocabularyTerm.id == SeriesTestItem.test_item_term_id)
        .where(SeriesTestItem.series_id.in_(series_ids))
        .order_by(SeriesTestItem.created_at)
    ).all()
    out: dict[uuid.UUID, list[str]] = {}
    for series_id, value in rows:
        out.setdefault(series_id, []).append(value)
    return out


#: 계열 종류를 사람 말로. **본체와 부속이 한 줄씩 섞이면** 「우리가 무슨 장비를
#: 가졌나」 가 안 보인다.
KIND_LABEL = {
    "main": "본체",
    "accessory": "부속",
    "sensor": "센서",
    "software": "소프트웨어",
}


#: 카탈로그 상태를 사람 말로.
CATALOG_STATUS_LABEL = {"active": "현행", "discontinued": "단종"}


def _options(db: Session, counts: list[tuple[uuid.UUID, int]]) -> list[FilterOption]:
    """용어 id 와 수를 **이름 붙은 선택지**로. 이름은 한 번에 꺼낸다."""
    names = _term_values(db, {term_id for term_id, _ in counts})
    out = [
        FilterOption(value=str(term_id), label=names.get(term_id, "—"), count=count)
        for term_id, count in counts
    ]
    return sorted(out, key=lambda one: (-one.count, one.label))


def _counted(db: Session, column: Any, where: Any) -> list[tuple[Any, int]]:
    rows = db.execute(
        select(column, func.count()).where(where, column.is_not(None)).group_by(column)
    ).all()
    return [(row[0], row[1]) for row in rows]


def series_filter_options(db: Session) -> CatalogFilterOptionsOut:
    """계열 목록의 열마다 고를 수 있는 값과 그 수.

    **카탈로그에 실제로 쓰인 값만 준다.** 제조사 축에는 수백 종이 있지만 계열이
    가리키는 것은 79종이고, 나머지는 골라도 0 건인 선택지가 된다 — 한 번 겪으면
    사람은 거르기를 안 믿는다.
    """
    alive = EquipmentSeries.deleted_at.is_(None)
    return CatalogFilterOptionsOut(
        makers=_options(db, _counted(db, EquipmentSeries.maker_term_id, alive)),
        # 분류는 군을 합쳐 올린다 — 「기계 시험기 전부」 를 한 번에 고를 수 있게.
        categories=rollup(db, dict(_counted(db, EquipmentSeries.category_term_id, alive))),
        kinds=[
            FilterOption(value=kind, label=KIND_LABEL.get(kind, kind), count=count)
            for kind, count in sorted(
                _counted(db, EquipmentSeries.kind, alive), key=lambda one: -one[1]
            )
        ],
        statuses=[
            FilterOption(
                value=status, label=CATALOG_STATUS_LABEL.get(status, status), count=count
            )
            for status, count in sorted(
                _counted(db, EquipmentSeries.status, alive), key=lambda one: -one[1]
            )
        ],
        series=[],
    )


def model_filter_options(db: Session) -> CatalogFilterOptionsOut:
    """기종 목록의 열마다 고를 수 있는 값과 그 수.

    제조사·분류는 **계열이 갖는 값**이라(ADR 0006) 계열을 거쳐 센다. 수는 그 값에
    해당하는 **기종 수**다 — 계열 수를 적으면 고른 뒤 나오는 줄 수와 안 맞고,
    그 어긋남은 거르기를 안 믿게 만든다.
    """
    alive = EquipmentModel.deleted_at.is_(None)

    def by_series(column: Any) -> list[tuple[uuid.UUID, int]]:
        rows = db.execute(
            select(column, func.count())
            .select_from(EquipmentModel)
            .join(EquipmentSeries, EquipmentSeries.id == EquipmentModel.series_id)
            .where(alive, column.is_not(None))
            .group_by(column)
        ).all()
        return [(row[0], row[1]) for row in rows]

    series_rows = db.execute(
        select(EquipmentSeries.id, EquipmentSeries.name, func.count())
        .select_from(EquipmentModel)
        .join(EquipmentSeries, EquipmentSeries.id == EquipmentModel.series_id)
        .where(alive)
        .group_by(EquipmentSeries.id, EquipmentSeries.name)
    ).all()
    return CatalogFilterOptionsOut(
        makers=_options(db, by_series(EquipmentSeries.maker_term_id)),
        categories=rollup(db, dict(by_series(EquipmentSeries.category_term_id))),
        kinds=[],
        statuses=[
            FilterOption(
                value=status, label=CATALOG_STATUS_LABEL.get(status, status), count=count
            )
            for status, count in sorted(
                _counted(db, EquipmentModel.status, alive), key=lambda one: -one[1]
            )
        ],
        series=sorted(
            [
                FilterOption(value=str(row[0]), label=row[1], count=row[2])
                for row in series_rows
            ],
            key=lambda one: (-one.count, one.label),
        ),
    )
