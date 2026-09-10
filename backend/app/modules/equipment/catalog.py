"""장비 카탈로그 — 계열과 기종, 그리고 사양서상 시험 항목.

보유 장비(`services.py`)와 나눈 이유는 ADR 0004 에 있다. 여기는 **제조사가 파는 것**
이고, 저기는 **우리가 가진 것**이다.

카탈로그가 다시 두 층인 이유는 ADR 0006 이다.

    계열(EquipmentSeries)   무슨 시험이 되나 · 어느 부속이 붙나 · 누가 만들었나
    기종(EquipmentModel)    수치가 갈리는 자리. 보유 장비가 가리키는 것

## 전사 공용이라 시스템 관리자만 고친다

한 부서가 계열의 분류나 사양을 고치면, 다른 부서가 가리키던 그 기종의 뜻이 바뀐다.
보유 장비가 소유 부서의 관리자 몫인 것과 다른 축이다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment import specs
from app.modules.equipment.models import (
    AVAILABLE_STATUSES,
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    ModelSpecValue,
    SeriesRelation,
    SpecSource,
)
from app.modules.equipment.schemas import (
    CitedMethodOut,
    EquipmentModelOut,
    EquipmentSeriesOut,
    ModelHeadlineSpecOut,
    ModelLimitOut,
    SeriesRelationOut,
    SeriesTestItemOut,
    SpecSourceOut,
)
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.resolve.services import resolve, resolve_term_id
from app.modules.test_items.models import (
    EquipmentTestCondition,
    EquipmentTestItem,
    SeriesTestCondition,
    SeriesTestItem,
    SeriesTestItemMethod,
)
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.modules.vocabulary.specs import SpecDefinition
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.pagination import Page
from app.shared.text import clean, compare_key


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


# --- 계열 --------------------------------------------------------------------


def _series_units(db: Session, series_id: uuid.UUID) -> list[Equipment]:
    return list(
        db.scalars(
            select(Equipment)
            .join(EquipmentModel, EquipmentModel.id == Equipment.model_id)
            .where(EquipmentModel.series_id == series_id, Equipment.deleted_at.is_(None))
        )
    )


def series_out(db: Session, row: EquipmentSeries, viewer: User) -> EquipmentSeriesOut:
    units = _series_units(db, row.id)
    source = db.get(SpecSource, row.source_id) if row.source_id else None
    models = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentModel)
            .where(EquipmentModel.series_id == row.id, EquipmentModel.deleted_at.is_(None))
        )
        or 0
    )
    return EquipmentSeriesOut(
        id=row.id,
        name=row.name,
        name_ko=row.name_ko,
        maker=_term_value(db, row.maker_term_id),
        maker_term_id=row.maker_term_id,
        brand=row.brand,
        category=_term_value(db, row.category_term_id),
        category_term_id=row.category_term_id,
        kind=row.kind,
        drive=_term_value(db, row.drive_term_id),
        drive_term_id=row.drive_term_id,
        form_factor=_term_value(db, row.form_factor_term_id),
        form_factor_term_id=row.form_factor_term_id,
        status=row.status,
        summary=row.summary,
        spec_note=row.spec_note,
        source_id=row.source_id,
        source_path=source.path if source else None,
        raw_limits=row.raw_limits or {},
        model_count=models,
        unit_count=len(units),
        operational_count=sum(1 for one in units if one.status in AVAILABLE_STATUSES),
        test_items=_test_items(db, row.id),
        relations=_relations(db, row.id),
        created_at=row.created_at,
        can_edit=viewer.is_system_admin,
    )


def list_series(
    db: Session,
    viewer: User,
    *,
    query: str | None,
    kind: str | None,
    category_term_id: uuid.UUID | None,
    owned: bool = False,
    issue: str | None = None,
    limit: int,
    offset: int,
) -> Page[EquipmentSeriesOut]:
    stmt = select(EquipmentSeries).where(EquipmentSeries.deleted_at.is_(None))
    if owned:
        # 보유 장비가 가리키는 기종이 속한 계열만. 「우리 것」 의 정의가 여기다 —
        # 계열은 보유의 단위가 아니라서 두 단계를 거쳐야 한다.
        stmt = stmt.where(
            EquipmentSeries.id.in_(
                select(EquipmentModel.series_id).where(
                    EquipmentModel.id.in_(
                        select(Equipment.model_id).where(
                            Equipment.model_id.is_not(None), Equipment.deleted_at.is_(None)
                        )
                    )
                )
            )
        )
    if issue == "test_items":
        stmt = stmt.where(
            EquipmentSeries.id.not_in(select(SeriesTestItem.series_id).distinct())
        )
    if kind:
        stmt = stmt.where(EquipmentSeries.kind == kind)
    if category_term_id is not None:
        stmt = stmt.where(EquipmentSeries.category_term_id == category_term_id)
    if query:
        # 이름·한글 이름·제조사를 다 본다 — 사람은 「인스트론」 으로도 찾고
        # 「6800」 으로도 찾고 「만능재료시험기」 로도 찾는다.
        text = f"%{clean(query)}%"
        makers = select(VocabularyTerm.id).where(VocabularyTerm.value.ilike(text))
        stmt = stmt.where(
            EquipmentSeries.name.ilike(text)
            | EquipmentSeries.name_ko.ilike(text)
            | EquipmentSeries.maker_term_id.in_(makers)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(EquipmentSeries.name).limit(limit).offset(offset))
    return Page(
        items=[series_out(db, row, viewer) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _resolved(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """이름으로 온 참조를 id 로 바꾼다. **하나로 안 정해지면 거절한다.**

    쓰기 API 가 이름을 받는 이유: AI 는 이름을 알지 id 를 모른다. 매 호출마다 id 를
    찾아 오는 왕복을 시키면, 왕복이 잦아진 AI 는 지름길(추측)을 택한다.

    그렇다고 비슷한 것을 골라 주지는 않는다 — 여기서 첫 줄을 집으면 그 선택은
    아무 데도 안 남고, 틀렸을 때 찾을 방법이 없다(ADR 0003 과 같은 규칙).
    """
    out = dict(payload)
    if out.get("maker_term_id") is None and out.get("maker"):
        out["maker_term_id"] = resolve_term_id(db, "manufacturer", out["maker"], field="maker")
    if out.get("category_term_id") is None and out.get("category"):
        out["category_term_id"] = resolve_term_id(
            db, "equipment_category", out["category"], field="category"
        )
    if out.get("test_item_term_id") is None and out.get("test_item"):
        out["test_item_term_id"] = resolve_term_id(
            db, "test_item", out["test_item"], field="test_item"
        )
    out.pop("maker", None)
    out.pop("category", None)
    out.pop("test_item", None)
    return out


def create_series(db: Session, actor: User, payload: dict[str, Any]) -> EquipmentSeries:
    payload = _resolved(db, payload)
    name = clean(payload["name"])
    normalized = compare_key(name)
    maker_id = payload.get("maker_term_id")

    # **같은 제조사에 같은 계열명이 둘 있으면 어느 쪽을 가리켰는지 알 수 없다.**
    # 비교키로 본다 — `6800` 과 `6800 ` 은 눈에 같아 보이는데 DB 는 다르게 본다.
    clash = db.scalar(
        select(EquipmentSeries).where(
            EquipmentSeries.normalized == normalized,
            EquipmentSeries.maker_term_id.is_(maker_id)
            if maker_id is None
            else EquipmentSeries.maker_term_id == maker_id,
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-CATALOG-0010",
            f"이미 있는 계열입니다: {clash.name}",
            details={"series_id": str(clash.id), "name": clash.name},
        )

    row = EquipmentSeries(
        name=name,
        name_ko=payload.get("name_ko"),
        normalized=normalized,
        maker_term_id=maker_id,
        brand=payload.get("brand"),
        category_term_id=payload.get("category_term_id"),
        kind=payload.get("kind") or "main",
        drive_term_id=payload.get("drive_term_id"),
        form_factor_term_id=payload.get("form_factor_term_id"),
        summary=payload.get("summary"),
        spec_note=payload.get("spec_note"),
        source_id=payload.get("source_id"),
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action=audit.CATALOG_CREATED,
        actor=actor,
        target_table="equipment_series",
        target_id=row.id,
        target_label=row.name,
    )
    db.commit()
    db.refresh(row)
    return row


def update_series(
    db: Session, series_id: uuid.UUID, changes: dict[str, Any]
) -> EquipmentSeries:
    """**보낸 것만 바꾼다.** changes 는 exclude_unset 으로 만들어진 dict 다."""
    changes = _resolved(db, changes)
    row = get_series(db, series_id)

    if "name" in changes and changes["name"] is not None:
        row.name = clean(changes["name"])
        row.normalized = compare_key(row.name)
    for field in (
        "name_ko",
        "maker_term_id",
        "brand",
        "category_term_id",
        "kind",
        "drive_term_id",
        "form_factor_term_id",
        "status",
        "summary",
        "spec_note",
        "source_id",
    ):
        if field in changes:
            setattr(row, field, changes[field])

    db.commit()
    db.refresh(row)
    return row


def delete_series(db: Session, series_id: uuid.UUID) -> None:
    """소프트 삭제.

    **든 기종이 있으면 거절한다.** 계열을 지우면 그 기종들이 무엇이었는지 알 수
    없게 된다 — 단종은 지우는 것이 아니라 `status` 로 적는다.
    """
    row = get_series(db, series_id)
    using = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentModel)
            .where(EquipmentModel.series_id == row.id, EquipmentModel.deleted_at.is_(None))
        )
        or 0
    )
    if using:
        raise Conflict(
            "TSC-CATALOG-0011",
            f"이 계열에 기종이 {using}개 있습니다. 먼저 기종을 정리하거나, "
            f"지우는 대신 상태를 단종으로 바꾸세요.",
        )
    row.deleted_at = datetime.now(UTC)
    db.commit()


# --- 계열 관계 ---------------------------------------------------------------


def add_relation(
    db: Session, series_id: uuid.UUID, payload: dict[str, Any]
) -> SeriesRelationOut:
    host = get_series(db, series_id)
    part = get_series(db, payload["part_series_id"])
    if host.id == part.id:
        raise AppError(
            "TSC-CATALOG-0012", "자기 자신과는 관계를 맺을 수 없습니다.", status=400
        )

    clash = db.scalar(
        select(SeriesRelation).where(
            SeriesRelation.host_series_id == host.id,
            SeriesRelation.part_series_id == part.id,
            SeriesRelation.relation == payload["relation"],
        )
    )
    if clash is not None:
        raise Conflict("TSC-CATALOG-0013", "같은 관계가 이미 있습니다.")

    row = SeriesRelation(
        host_series_id=host.id,
        part_series_id=part.id,
        relation=payload["relation"],
        note=payload.get("note"),
    )
    db.add(row)
    db.commit()
    return next(one for one in _relations(db, host.id) if one.id == row.id)


def delete_relation(db: Session, series_id: uuid.UUID, relation_id: uuid.UUID) -> None:
    row = db.get(SeriesRelation, relation_id)
    if row is None or series_id not in (row.host_series_id, row.part_series_id):
        raise NotFound("TSC-CATALOG-0014", "관계를 찾을 수 없습니다.")
    db.delete(row)
    db.commit()


# --- 대표 사양 ---------------------------------------------------------------

#: 목록 한 줄에 몇 칸까지 그리나.
#:
#: **셋을 넘기면 이름이 밀린다.** 좁은 화면에서 먼저 접히는 것이 기종명이면 그 줄은
#: 아무 쓸모가 없다 — 사람이 라벨과 대조하는 것이 그 이름이다.
HEADLINE_MAX = 3

#: 분류가 대표를 안 정했을 때 대신 그릴 칸 수. 대표보다 적게 둔다 — 고른 것이 아니라
#: **대신하는 것**이라, 같은 자리를 같은 무게로 채우면 그 차이가 안 보인다.
HEADLINE_FALLBACK = 2


def _headline_specs(
    db: Session, models: list[EquipmentModel]
) -> dict[uuid.UUID, list[ModelHeadlineSpecOut]]:
    """기종마다 목록에 그릴 사양 두어 칸. **여러 기종을 한 번에 본다.**

    ## 고르는 순서

        1. 분류가 정한 것      온톨로지 `categories.json` 의 headline_specs
        2. 검색축에 이어진 것  이 시스템이 「판단에 쓴다」 고 이미 표시해 둔 사양

    2 가 있는 이유: 대표를 안 적어 둔 분류에서 이 칸이 통째로 비면 그 화면은 「사양이
    없다」 로 읽힌다 — 실제로는 **적을 자리를 안 정한 것**이고, 그 둘은 할 일이 다르다.

    ## 값이 없는 칸은 안 보낸다

    분류가 「하중 용량」 을 대표로 정했어도 이 기종에 그 값이 없으면 안 싣는다. 라벨만
    그려진 빈 칸은 「0 이다」 로도 「모른다」 로도 읽히는데, 그 둘은 장비를 고르는
    사람에게 정반대다. 대신 화면이 `spec_count` 로 「사양 없음」 을 말한다.

    ## 한 번에 보는 이유

    한 줄씩 조회하면 200줄짜리 목록이 조회를 수백 번 한다. 카탈로그가 커질수록
    나빠지고, 그때는 목록이 먼저 죽는다.
    """
    if not models:
        return {}

    series_of: dict[uuid.UUID, uuid.UUID | None] = {}
    for series in db.scalars(
        select(EquipmentSeries).where(
            EquipmentSeries.id.in_({one.series_id for one in models})
        )
    ):
        series_of[series.id] = series.category_term_id

    wanted: dict[uuid.UUID, list[str]] = {}
    term_ids = {one for one in series_of.values() if one is not None}
    if term_ids:
        for term in db.scalars(select(VocabularyTerm).where(VocabularyTerm.id.in_(term_ids))):
            keys = term.attributes.get("headline_specs")
            if isinstance(keys, list):
                wanted[term.id] = [str(key) for key in keys][:HEADLINE_MAX]

    fallback = list(
        db.scalars(
            select(SpecDefinition)
            .where(SpecDefinition.condition_key_id.is_not(None))
            .order_by(SpecDefinition.sort_order, SpecDefinition.label)
        )
    )
    definitions: dict[str, SpecDefinition] = {row.key: row for row in fallback}
    named = {key for keys in wanted.values() for key in keys} - set(definitions)
    if named:
        for row in db.scalars(select(SpecDefinition).where(SpecDefinition.key.in_(named))):
            definitions[row.key] = row
    if not definitions:
        return {}

    held: dict[uuid.UUID, dict[uuid.UUID, ModelSpecValue]] = {}
    for value in db.scalars(
        select(ModelSpecValue).where(
            ModelSpecValue.model_id.in_([one.id for one in models]),
            ModelSpecValue.definition_id.in_({row.id for row in definitions.values()}),
        )
    ):
        held.setdefault(value.model_id, {})[value.definition_id] = value

    out: dict[uuid.UUID, list[ModelHeadlineSpecOut]] = {}
    for model in models:
        mine = held.get(model.id)
        if not mine:
            continue
        term_id = series_of.get(model.series_id)
        picked = [
            definitions[key]
            for key in (wanted.get(term_id) if term_id else None) or []
            if key in definitions and definitions[key].id in mine
        ]
        if not picked:
            picked = [row for row in fallback if row.id in mine][:HEADLINE_FALLBACK]
        out[model.id] = [
            ModelHeadlineSpecOut(
                definition_id=definition.id,
                key=definition.key,
                label=definition.label,
                kind=definition.kind,
                si_unit=definition.si_unit,
                display_unit=definition.display_unit,
                num_value=mine[definition.id].num_value,
                num_min=mine[definition.id].num_min,
                num_max=mine[definition.id].num_max,
                text_value=mine[definition.id].text_value,
                bool_value=mine[definition.id].bool_value,
            )
            for definition in picked
        ]
    return out


def _spec_counts(db: Session, model_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """기종마다 사양이 몇 칸 적혔나.

    **0 인 기종은 목록이 말해 줘야 한다** — 그 기종으로 등록하는 장비는 조건 없이
    복사되고, 검색은 그것을 「모름」 으로 답한다.
    """
    if not model_ids:
        return {}
    rows = db.execute(
        select(ModelSpecValue.model_id, func.count())
        .where(ModelSpecValue.model_id.in_(model_ids))
        .group_by(ModelSpecValue.model_id)
    ).all()
    return {model_id: count for model_id, count in rows}


# --- 기종 --------------------------------------------------------------------


def model_out(
    db: Session,
    row: EquipmentModel,
    viewer: User,
    *,
    headline: list[ModelHeadlineSpecOut] | None = None,
    spec_count: int | None = None,
) -> EquipmentModelOut:
    """기종 한 줄.

    대표 사양과 사양 칸 수는 **목록이 한 번에 구해 넘긴다**(`list_models`). 안 넘기면
    여기서 혼자 구한다 — 상세 한 건이 목록의 사정을 알 필요는 없다.
    """
    series = db.get(EquipmentSeries, row.series_id)
    if headline is None:
        headline = _headline_specs(db, [row]).get(row.id, [])
    if spec_count is None:
        spec_count = _spec_counts(db, [row.id]).get(row.id, 0)
    units = db.scalars(
        select(Equipment).where(Equipment.model_id == row.id, Equipment.deleted_at.is_(None))
    ).all()
    return EquipmentModelOut(
        id=row.id,
        series_id=row.series_id,
        series_name=series.name if series else "",
        name=row.name,
        name_ko=row.name_ko,
        maker=_term_value(db, series.maker_term_id) if series else None,
        maker_term_id=series.maker_term_id if series else None,
        category=_term_value(db, series.category_term_id) if series else None,
        category_term_id=series.category_term_id if series else None,
        form_factor=_term_value(db, row.form_factor_term_id),
        form_factor_term_id=row.form_factor_term_id,
        status=row.status,
        summary=row.summary,
        spec_note=row.spec_note,
        raw_specs=row.raw_specs or {},
        unit_count=len(units),
        # **대수만 보면 여유 있어 보인다.** 다섯 대 중 한 대만 가동인 경우가 있다.
        operational_count=sum(1 for one in units if one.status in AVAILABLE_STATUSES),
        test_items=_test_items(db, row.series_id),
        headline_specs=headline,
        spec_count=spec_count,
        created_at=row.created_at,
        can_edit=viewer.is_system_admin,
    )


def list_models(
    db: Session,
    viewer: User,
    *,
    query: str | None,
    series_id: uuid.UUID | None,
    owned: bool = False,
    issue: str | None = None,
    limit: int,
    offset: int,
) -> Page[EquipmentModelOut]:
    """기종 목록.

    ## owned · issue 는 「채울 자리」 를 위한 것이다

    카탈로그 564개 중 사양이 빈 것이 112개다. 그 전부를 채우라고 하면 아무도 안
    채운다 — **우리가 실제로 가진 것**부터 보여 주면 그 목록은 끝이 있다.
    홈의 「남은 일」 이 이 필터로 링크한다.
    """
    stmt = select(EquipmentModel).where(EquipmentModel.deleted_at.is_(None))
    if series_id is not None:
        stmt = stmt.where(EquipmentModel.series_id == series_id)
    if owned:
        stmt = stmt.where(
            EquipmentModel.id.in_(
                select(Equipment.model_id).where(
                    Equipment.model_id.is_not(None), Equipment.deleted_at.is_(None)
                )
            )
        )
    if issue == "specs":
        stmt = stmt.where(EquipmentModel.id.not_in(select(ModelSpecValue.model_id).distinct()))
    elif issue == "uncertain":
        # 반입이 「원본을 잘못 읽었을 수 있다」 고 표시한 것. 사람이 원본을 열어
        # 확인해야 하는 자리다.
        stmt = stmt.where(EquipmentModel.spec_note.ilike("%원본 확인 필요%"))
    if query:
        # 기종명·한글명·계열명·제조사를 다 본다. 사람이 아는 조각이 어느 것일지
        # 우리가 정할 수 없다.
        text = f"%{clean(query)}%"
        makers = select(VocabularyTerm.id).where(VocabularyTerm.value.ilike(text))
        series = select(EquipmentSeries.id).where(
            EquipmentSeries.name.ilike(text)
            | EquipmentSeries.name_ko.ilike(text)
            | EquipmentSeries.maker_term_id.in_(makers)
        )
        stmt = stmt.where(
            EquipmentModel.name.ilike(text)
            | EquipmentModel.name_ko.ilike(text)
            | EquipmentModel.series_id.in_(series)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(EquipmentModel.name).limit(limit).offset(offset)))
    # **한 번에 구한다.** 줄마다 구하면 200줄짜리 목록이 조회를 수백 번 한다.
    headlines = _headline_specs(db, rows)
    counts = _spec_counts(db, [row.id for row in rows])
    return Page(
        items=[
            model_out(
                db,
                row,
                viewer,
                headline=headlines.get(row.id, []),
                spec_count=counts.get(row.id, 0),
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def _series_of(db: Session, payload: dict[str, Any]) -> EquipmentSeries:
    """계열을 id 나 이름으로 집는다. **못 정하면 거절한다.**"""
    if payload.get("series_id") is not None:
        return get_series(db, payload["series_id"])
    if payload.get("series"):
        answer = resolve(
            db,
            {
                "kind": "series",
                "text": payload["series"],
                "maker": payload.get("maker"),
                "limit": 5,
            },
        )
        if answer.match == "exact" and answer.id is not None:
            return get_series(db, answer.id)
        raise AppError(
            "TSC-CATALOG-0015",
            f"계열 「{payload['series']}」 을(를) 하나로 정할 수 없습니다. "
            f"series_id 로 주거나 계열을 먼저 만드세요.",
            status=400,
            details={
                "candidates": [
                    {"id": str(one.id), "label": one.label} for one in answer.candidates
                ]
            },
        )
    raise AppError(
        "TSC-CATALOG-0016",
        "계열이 필요합니다. 단품이면 기종 하나짜리 계열을 먼저 만드세요.",
        status=400,
    )


def create_model(db: Session, actor: User, payload: dict[str, Any]) -> EquipmentModel:
    series = _series_of(db, payload)
    name = clean(payload["name"])
    normalized = compare_key(name)

    clash = db.scalar(
        select(EquipmentModel).where(
            EquipmentModel.series_id == series.id, EquipmentModel.normalized == normalized
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-CATALOG-0002",
            f"이 계열에 이미 있는 기종입니다: {clash.name}",
            details={"model_id": str(clash.id), "name": clash.name},
        )

    row = EquipmentModel(
        series_id=series.id,
        name=name,
        name_ko=payload.get("name_ko"),
        normalized=normalized,
        form_factor_term_id=payload.get("form_factor_term_id"),
        summary=payload.get("summary"),
        spec_note=payload.get("spec_note"),
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action=audit.CATALOG_CREATED,
        actor=actor,
        target_table="equipment_models",
        target_id=row.id,
        target_label=f"{series.name} / {row.name}",
    )
    db.commit()
    db.refresh(row)
    return row


def update_model(db: Session, model_id: uuid.UUID, changes: dict[str, Any]) -> EquipmentModel:
    """**보낸 것만 바꾼다.** changes 는 exclude_unset 으로 만들어진 dict 다."""
    row = get_model(db, model_id)

    if changes.get("series_id") is not None:
        row.series_id = get_series(db, changes["series_id"]).id
    if "name" in changes and changes["name"] is not None:
        row.name = clean(changes["name"])
        row.normalized = compare_key(row.name)
    for field in ("name_ko", "form_factor_term_id", "status", "summary", "spec_note"):
        if field in changes:
            setattr(row, field, changes[field])

    db.commit()
    db.refresh(row)
    return row


def delete_model(db: Session, model_id: uuid.UUID) -> None:
    """소프트 삭제.

    **가리키는 장비가 있으면 거절한다.** 지우면 그 장비가 무엇이었는지 알 수 없게
    된다 — 단종은 지우는 것이 아니라 `status` 로 적는다.
    """
    row = get_model(db, model_id)
    using = (
        db.scalar(
            select(func.count())
            .select_from(Equipment)
            .where(Equipment.model_id == row.id, Equipment.deleted_at.is_(None))
        )
        or 0
    )
    if using:
        raise Conflict(
            "TSC-CATALOG-0003",
            f"이 기종을 가리키는 보유 장비가 {using}대 있습니다. "
            f"지우는 대신 상태를 단종으로 바꾸세요.",
        )
    row.deleted_at = datetime.now(UTC)
    db.commit()


# --- 계열의 시험 항목 편집 -----------------------------------------------------------


def _method_id(db: Session, code: str | None) -> uuid.UUID | None:
    """규격 번호로 시험법을 집는다. **못 정하면 거절한다.**"""
    if not code:
        return None
    answer = resolve(db, {"kind": "method", "text": code, "limit": 5})
    if answer.match == "exact" and answer.id is not None:
        return answer.id
    raise AppError(
        "TSC-CATALOG-0018",
        f"시험법 「{code}」 을(를) 하나로 정할 수 없습니다.",
        status=400,
        details={
            "candidates": [
                {"id": str(one.id), "label": one.label} for one in answer.candidates
            ]
        },
    )


def add_test_item(
    db: Session, series_id: uuid.UUID, payload: dict[str, Any]
) -> SeriesTestItemOut:
    series = get_series(db, series_id)
    payload = _resolved(db, payload)
    method_id = payload.get("method_id") or _method_id(db, payload.get("method_code"))
    if payload.get("test_item_term_id") is None:
        raise AppError(
            "TSC-CATALOG-0017",
            "시험 항목이 필요합니다. test_item_term_id 나 test_item(이름)을 주세요.",
            status=400,
        )
    clash = db.scalar(
        select(SeriesTestItem).where(
            SeriesTestItem.series_id == series.id,
            SeriesTestItem.test_item_term_id == payload["test_item_term_id"],
            SeriesTestItem.method_id.is_(None)
            if method_id is None
            else SeriesTestItem.method_id == method_id,
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-CATALOG-0004",
            "같은 시험 항목·시험법의 시험 항목이 이미 있습니다. 그것을 고치세요.",
            details={"equipment_test_item_id": str(clash.id)},
        )

    row = SeriesTestItem(
        series_id=series.id,
        test_item_term_id=payload["test_item_term_id"],
        method_id=method_id,
        note=payload.get("note"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return next(one for one in _test_items(db, series.id) if one.id == row.id)


def delete_test_item(
    db: Session, series_id: uuid.UUID, equipment_test_item_id: uuid.UUID
) -> None:
    series = get_series(db, series_id)
    row = db.get(SeriesTestItem, equipment_test_item_id)
    if row is None or row.series_id != series.id:
        raise NotFound("TSC-CATALOG-0005", "시험 항목을 찾을 수 없습니다.")
    db.delete(row)
    db.commit()


def upsert_limit(
    db: Session,
    series_id: uuid.UUID,
    equipment_test_item_id: uuid.UUID,
    payload: dict[str, Any],
) -> ModelLimitOut:
    """조건 한 칸을 넣거나 덮어쓴다.

    **계열 전체가 만족하는 것만 여기 적는다.** 기종마다 갈리는 수치는 그 기종의
    사양에 적고, 보유 장비를 만들 때 합쳐진다 — 여기 적으면 0.5 kN 짜리에도
    300 kN 이 붙는다(ADR 0006).
    """
    series = get_series(db, series_id)
    test_item = db.get(SeriesTestItem, equipment_test_item_id)
    if test_item is None or test_item.series_id != series.id:
        raise NotFound("TSC-CATALOG-0005", "시험 항목을 찾을 수 없습니다.")

    key = db.get(ConditionKey, payload["condition_key_id"])
    if key is None:
        raise NotFound("TSC-CATALOG-0006", "조건 정의를 찾을 수 없습니다.")

    low, high = payload.get("min_value"), payload.get("max_value")
    if low is not None and high is not None and low > high:
        # **거꾸로 넣은 범위는 복사된 뒤 검색에서 아무것도 안 맞는다.** 조용히
        # 통과시키면 그 원인은 카탈로그가 아니라 장비 쪽에서 찾게 된다.
        raise AppError(
            "TSC-CATALOG-0007", f"{key.label}의 최소가 최대보다 큽니다.", status=400
        )

    existing = db.scalar(
        select(SeriesTestCondition).where(
            SeriesTestCondition.series_test_item_id == test_item.id,
            SeriesTestCondition.condition_key_id == key.id,
        )
    )
    target = existing or SeriesTestCondition(
        series_test_item_id=test_item.id, condition_key_id=key.id
    )
    target.min_value = low
    target.max_value = high
    target.text_value = payload.get("text_value")
    target.note = payload.get("note")
    if existing is None:
        db.add(target)
    db.commit()

    return next(one for one in _limits(db, test_item.id) if one.condition_key_id == key.id)


def delete_limit(
    db: Session, series_id: uuid.UUID, equipment_test_item_id: uuid.UUID, limit_id: uuid.UUID
) -> None:
    series = get_series(db, series_id)
    test_item = db.get(SeriesTestItem, equipment_test_item_id)
    if test_item is None or test_item.series_id != series.id:
        raise NotFound("TSC-CATALOG-0005", "시험 항목을 찾을 수 없습니다.")
    target = db.get(SeriesTestCondition, limit_id)
    if target is None or target.series_test_item_id != test_item.id:
        raise NotFound("TSC-CATALOG-0008", "조건을 찾을 수 없습니다.")
    db.delete(target)
    db.commit()


# --- 복사 --------------------------------------------------------------------


def copy_test_items_to(db: Session, equipment: Equipment, actor: User) -> int:
    """카탈로그의 시험 항목을 이 장비로 **복사한다.** 새로 만든 시험 항목 수를 돌려준다.

    ## 두 곳에서 끌어온다

    **무엇이 되나**는 그 기종이 속한 계열의 시험 항목에서, **어디까지 되나**는 그
    기종의 사양에서 온다. 계열 조건은 봉투이고 기종 사양은 그 기종의 것이라,
    같은 조건이 양쪽에 있으면 **기종 사양이 이긴다** — 0.5 kN 짜리에 계열 봉투인
    300 kN 이 붙으면 검색이 없는 능력을 있다고 답한다(ADR 0006).

    ## 상속이 아니라 복사인 이유

    같은 기종이라도 챔버를 뗀 대가 있고, 지그가 달라 굽힘이 안 되는 대가 있다.
    **갈라지는 것이 정상**이고, 갈라진 것이 보여야 한다. 상속으로 두면 검색이
    "개체 값인가 카탈로그 값인가" 를 매번 되짚어야 하고, 그 되짚기를 한 화면에서
    빠뜨리면 결과가 조용히 갈린다(ADR 0004).

    ## confidence 는 catalog 다

    사양서에서 온 값이지 해 본 값이 아니라는 뜻이 이미 그 칸에 있다. 실제로 돌려
    본 사람이 verified 로 올린다.

    ## 이미 있는 것은 안 덮는다

    덮으면 손으로 고쳐 둔 실측이 조용히 사라진다. **커밋은 부르는 쪽이 한다** —
    장비 생성과 같은 트랜잭션에 있어야 "장비는 생겼는데 시험 항목만 없는" 상태가 안 된다.
    """
    if equipment.model_id is None:
        return 0
    model = db.get(EquipmentModel, equipment.model_id)
    if model is None:
        return 0

    derived = specs.conditions_from_specs(db, model.id)

    made = 0
    for source in db.scalars(
        select(SeriesTestItem).where(SeriesTestItem.series_id == model.series_id)
    ):
        exists = db.scalar(
            select(EquipmentTestItem).where(
                EquipmentTestItem.equipment_id == equipment.id,
                EquipmentTestItem.test_item_term_id == source.test_item_term_id,
                EquipmentTestItem.method_id.is_(None)
                if source.method_id is None
                else EquipmentTestItem.method_id == source.method_id,
            )
        )
        if exists is not None:
            continue

        copied = EquipmentTestItem(
            equipment_id=equipment.id,
            test_item_term_id=source.test_item_term_id,
            method_id=source.method_id,
            confidence="catalog",
            note=source.note,
            created_by_id=actor.id,
        )
        db.add(copied)
        db.flush()

        limits: dict[uuid.UUID, dict[str, Any]] = {}
        for limit in db.scalars(
            select(SeriesTestCondition).where(
                SeriesTestCondition.series_test_item_id == source.id
            )
        ):
            limits[limit.condition_key_id] = {
                "min_value": limit.min_value,
                "max_value": limit.max_value,
                "text_value": limit.text_value,
                "note": limit.note,
            }
        for key_id, (low, high, label) in derived.items():
            # 기종 사양이 계열 봉투를 이긴다. 어느 사양에서 왔는지 남긴다 —
            # 반년 뒤 이 숫자를 물을 사람이 볼 자리가 여기밖에 없다.
            limits[key_id] = {
                "min_value": low,
                "max_value": high,
                "text_value": None,
                "note": f"사양 {label}에서 따옴",
            }

        for key_id, values in limits.items():
            db.add(
                EquipmentTestCondition(
                    equipment_test_item_id=copied.id, condition_key_id=key_id, **values
                )
            )
        made += 1
    return made


# --- 사양 출처 ---------------------------------------------------------------


def list_sources(
    db: Session, *, query: str | None, limit: int, offset: int
) -> Page[SpecSourceOut]:
    stmt = select(SpecSource)
    if query:
        text = f"%{clean(query)}%"
        stmt = stmt.where(SpecSource.path.ilike(text) | SpecSource.title.ilike(text))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(SpecSource.path).limit(limit).offset(offset))
    return Page(
        items=[
            SpecSourceOut(
                id=row.id,
                path=row.path,
                title=row.title,
                maker=_term_value(db, row.maker_term_id),
                pages=row.pages,
                published_on=row.published_on,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
