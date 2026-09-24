"""계열 — 무슨 시험이 되나 · 어느 부속이 붙나 · 누가 만들었나.
목록·만들기·고치기·관계·시험 항목 편집·보유 장비로 복사.

`catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes import filters as attribute_filters
from app.modules.attributes import services as attributes
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.equipment import specs
from app.modules.equipment.catalog_common import (
    _limits,
    _model_counts,
    _relations,
    _term_value,
    _term_values,
    _test_item_names,
    _test_items,
    _unit_counts,
    get_series,
)
from app.modules.equipment.category_tree import family
from app.modules.equipment.models import (
    AVAILABLE_STATUSES,
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    SeriesRelation,
    SpecSource,
)
from app.modules.equipment.schemas import (
    EquipmentSeriesOut,
    EquipmentSeriesRow,
    ModelLimitOut,
    PendingMethodOut,
    SeriesRelationOut,
    SeriesTestItemOut,
)
from app.modules.methods.models import TestMethod, TestMethodItem
from app.modules.methods.services import promote_pending
from app.modules.resolve.services import resolve, resolve_term_id
from app.modules.test_items.models import (
    EquipmentTestCondition,
    EquipmentTestItem,
    SeriesPendingMethod,
    SeriesTestCondition,
    SeriesTestItem,
)
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.pagination import Page
from app.shared.text import clean, compare_key

# --- 계열 --------------------------------------------------------------------


def _series_units(db: Session, series_id: uuid.UUID) -> list[Equipment]:
    return list(
        db.scalars(
            select(Equipment)
            .join(EquipmentModel, EquipmentModel.id == Equipment.model_id)
            .where(EquipmentModel.series_id == series_id, Equipment.deleted_at.is_(None))
        )
    )


def _pending_methods(db: Session, series_id: uuid.UUID) -> list[PendingMethodOut]:
    """이 계열이 인용했는데 **어느 시험 항목의 것인지 아직 안 정해진** 규격.

    시험 항목 밑에 못 그리니 따로 보인다 — 안 보이면 「이 계열은 ASTM E8 을 인용했다」 가
    카탈로그 JSON 에만 남고, 화면을 보는 사람은 그 규격이 없는 줄 안다.
    """
    return [
        PendingMethodOut(id=row.id, code=row.code, title=row.title)
        for row in db.scalars(
            select(TestMethod)
            .join(SeriesPendingMethod, SeriesPendingMethod.method_id == TestMethod.id)
            .where(SeriesPendingMethod.series_id == series_id, TestMethod.deleted_at.is_(None))
            .order_by(TestMethod.code)
        )
    ]


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
        pending_methods=_pending_methods(db, row.id),
        relations=_relations(db, row.id),
        attributes=attributes.values_of(db, target="series", object_ids=[row.id])[row.id],
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
    name: str | None = None,
    maker_term_id: uuid.UUID | None = None,
    status: str | None = None,
    models: str | None = None,
    test_item: str | None = None,
    owned: bool = False,
    attrs: list[str] | None = None,
    limit: int,
    offset: int,
) -> Page[EquipmentSeriesRow]:
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
    if test_item == "none":
        # **이 계열의 기종으로 장비를 등록해도 복사될 시험 항목이 없다** — 그 장비는
        # 검색에 안 걸린다. 홈의 「남은 일」 이 세는 것과 같은 조건이라야 한다.
        stmt = stmt.where(
            EquipmentSeries.id.not_in(select(SeriesTestItem.series_id).distinct())
        )
    if models == "none":
        # 기종이 0 이면 **아무도 이 계열을 가리킬 수 없다** — 보유 장비가 가리키는
        # 것은 계열이 아니라 기종이다.
        stmt = stmt.where(
            EquipmentSeries.id.not_in(
                select(EquipmentModel.series_id).where(EquipmentModel.deleted_at.is_(None))
            )
        )
    if status:
        stmt = stmt.where(EquipmentSeries.status == status)
    if maker_term_id is not None:
        stmt = stmt.where(EquipmentSeries.maker_term_id == maker_term_id)
    if name:
        # **이 열만 본다.** `q` 는 제조사까지 보므로, 이름 칸에 친 글자가 제조사에
        # 걸린 줄을 함께 데려오면 그 줄들이 찾는 것을 가린다.
        text_only = f"%{clean(name)}%"
        stmt = stmt.where(
            EquipmentSeries.name.ilike(text_only) | EquipmentSeries.name_ko.ilike(text_only)
        )
    if kind:
        stmt = stmt.where(EquipmentSeries.kind == kind)
    if category_term_id is not None:
        # 군을 고르면 그 아래 유형이 다 걸린다(category_tree).
        stmt = stmt.where(EquipmentSeries.category_term_id.in_(family(db, category_term_id)))
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
    stmt = attribute_filters.apply(
        db,
        stmt,
        "series",
        EquipmentSeries.id,
        attribute_filters.parse(db, "series", attrs or []),
    )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(EquipmentSeries.name).limit(limit).offset(offset)))

    # **여기서부터는 줄 수와 무관하게 질의 넷이다.** 줄마다 채우면 50줄에 1,058회다.
    ids = [row.id for row in rows]
    terms = _term_values(
        db, {row.maker_term_id for row in rows} | {row.category_term_id for row in rows}
    )
    model_counts = _model_counts(db, ids)
    units = _unit_counts(db, EquipmentModel.series_id, ids, joined=EquipmentModel)
    items = _test_item_names(db, ids)
    return Page(
        items=[
            EquipmentSeriesRow(
                id=row.id,
                name=row.name,
                name_ko=row.name_ko,
                maker=terms.get(row.maker_term_id) if row.maker_term_id else None,
                brand=row.brand,
                category=(terms.get(row.category_term_id) if row.category_term_id else None),
                kind=row.kind,
                status=row.status,
                model_count=model_counts.get(row.id, 0),
                unit_count=units.get(row.id, (0, 0))[0],
                operational_count=units.get(row.id, (0, 0))[1],
                test_item_count=len(items.get(row.id, [])),
            )
            for row in rows
        ],
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
    if changes.get("attributes") is not None:
        attributes.set_values(
            db,
            None,
            target="series",
            object_id=row.id,
            items=[AttributeValueIn.model_validate(one) for one in changes["attributes"]],
        )

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
            f"지우는 대신 상태를 단종으로 바꾸십시오.",
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
            "시험 항목이 필요합니다. test_item_term_id 나 test_item(이름)을 주십시오.",
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
            "같은 시험 항목·시험법의 시험 항목이 이미 있습니다. 그것을 고치십시오.",
            details={"equipment_test_item_id": str(clash.id)},
        )

    row = SeriesTestItem(
        series_id=series.id,
        test_item_term_id=payload["test_item_term_id"],
        method_id=method_id,
        note=payload.get("note"),
    )
    db.add(row)
    db.flush()
    # 이 계열이 항목 미정으로 인용해 둔 규격 중 이 시험의 것이 있으면 지금 붙는다.
    for method in db.scalars(
        select(TestMethod)
        .join(SeriesPendingMethod, SeriesPendingMethod.method_id == TestMethod.id)
        .join(TestMethodItem, TestMethodItem.method_id == TestMethod.id)
        .where(
            SeriesPendingMethod.series_id == series.id,
            TestMethodItem.test_item_term_id == row.test_item_term_id,
        )
    ):
        promote_pending(db, method)
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
    target.requires_accessory = bool(payload.get("requires_accessory"))
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
                "requires_accessory": limit.requires_accessory,
                "note": limit.note,
            }
        for key_id, (low, high, label, accessory) in derived.items():
            # 기종 사양이 계열 봉투를 이긴다. 어느 사양에서 왔는지 남긴다 —
            # 반년 뒤 이 숫자를 물을 사람이 볼 자리가 여기밖에 없다. **부속 표시도
            # 따라간다** — 이것이 빠지면 챔버 옵션 온도가 이 대의 능력이 된다.
            limits[key_id] = {
                "min_value": low,
                "max_value": high,
                "text_value": None,
                "requires_accessory": accessory,
                "note": f"사양 {label}에서 따옴" + (" · 옵션 부속 기준" if accessory else ""),
            }

        for key_id, values in limits.items():
            db.add(
                EquipmentTestCondition(
                    equipment_test_item_id=copied.id, condition_key_id=key_id, **values
                )
            )
        made += 1
    return made
