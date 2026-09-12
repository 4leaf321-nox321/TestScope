"""기종 — 수치가 갈리는 자리, 보유 장비가 가리키는 것. 대표 사양·목록·만들기·고치기·사양 출처.

`catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment import free_specs
from app.modules.equipment.catalog_common import (
    _term_value,
    _term_values,
    _test_item_names,
    _test_items,
    _unit_counts,
    get_model,
    get_series,
)
from app.modules.equipment.category_tree import family
from app.modules.equipment.models import (
    AVAILABLE_STATUSES,
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    ModelSpecValue,
    SpecSource,
)
from app.modules.equipment.schemas import (
    EquipmentModelOut,
    EquipmentModelRow,
    ModelHeadlineSpecOut,
    SpecSourceOut,
)
from app.modules.resolve.services import resolve
from app.modules.test_items.models import (
    SeriesTestItem,
)
from app.modules.vocabulary.models import VocabularyTerm
from app.modules.vocabulary.specs import SpecDefinition
from app.shared import audit
from app.shared.errors import AppError, Conflict
from app.shared.pagination import Page
from app.shared.text import clean, compare_key

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
        free_specs=free_specs.list_out(db, row.id),
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
    name: str | None = None,
    maker_term_id: uuid.UUID | None = None,
    category_term_id: uuid.UUID | None = None,
    spec: str | None = None,
    test_item: str | None = None,
    owned: bool = False,
    limit: int,
    offset: int,
) -> Page[EquipmentModelRow]:
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
    if spec == "none":
        stmt = stmt.where(EquipmentModel.id.not_in(select(ModelSpecValue.model_id).distinct()))
    elif spec == "uncertain":
        # 반입이 「원본을 잘못 읽었을 수 있다」 고 표시한 것. 사람이 원본을 열어
        # 확인해야 하는 자리다.
        stmt = stmt.where(EquipmentModel.spec_note.ilike("%원본 확인 필요%"))
    # 제조사·분류·시험 항목은 **계열이 갖는 값**이다(ADR 0006) — 기종을 거르려면
    # 계열을 거쳐야 한다. 기종에 복사해 두면 한 계열 열 기종에 열 번 적히고,
    # 그 열 번이 언젠가 서로 달라진다.
    if maker_term_id is not None:
        stmt = stmt.where(
            EquipmentModel.series_id.in_(
                select(EquipmentSeries.id).where(
                    EquipmentSeries.maker_term_id == maker_term_id
                )
            )
        )
    if category_term_id is not None:
        stmt = stmt.where(
            EquipmentModel.series_id.in_(
                select(EquipmentSeries.id).where(
                    EquipmentSeries.category_term_id.in_(family(db, category_term_id))
                )
            )
        )
    if test_item == "none":
        stmt = stmt.where(
            EquipmentModel.series_id.not_in(select(SeriesTestItem.series_id).distinct())
        )
    if name:
        # **이 열만 본다.** `q` 는 계열명·제조사까지 보므로 따로 둔다.
        text_only = f"%{clean(name)}%"
        stmt = stmt.where(
            EquipmentModel.name.ilike(text_only) | EquipmentModel.name_ko.ilike(text_only)
        )
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

    # **한 번에 구한다.** 줄마다 구하면 50줄짜리 목록이 조회를 948회 한다.
    headlines = _headline_specs(db, rows)
    counts = _spec_counts(db, [row.id for row in rows])
    series_ids = [row.series_id for row in rows]
    series_of = {
        one.id: one
        for one in db.scalars(
            select(EquipmentSeries).where(EquipmentSeries.id.in_(series_ids))
        )
    }
    terms = _term_values(
        db,
        {row.form_factor_term_id for row in rows}
        | {one.maker_term_id for one in series_of.values()}
        | {one.category_term_id for one in series_of.values()},
    )
    units = _unit_counts(db, Equipment.model_id, [row.id for row in rows])
    items = _test_item_names(db, series_ids)

    def one_row(row: EquipmentModel) -> EquipmentModelRow:
        series = series_of.get(row.series_id)
        return EquipmentModelRow(
            id=row.id,
            series_id=row.series_id,
            series_name=series.name if series else "",
            name=row.name,
            name_ko=row.name_ko,
            # **제조사·분류는 계열이 갖는다**(ADR 0006) — 기종에 열 번 적히면 열 번
            # 다 같을 이유가 없다.
            maker=(
                terms.get(series.maker_term_id) if series and series.maker_term_id else None
            ),
            category=(
                terms.get(series.category_term_id)
                if series and series.category_term_id
                else None
            ),
            form_factor=(
                terms.get(row.form_factor_term_id) if row.form_factor_term_id else None
            ),
            status=row.status,
            unit_count=units.get(row.id, (0, 0))[0],
            operational_count=units.get(row.id, (0, 0))[1],
            test_items=items.get(row.series_id, []),
            headline_specs=headlines.get(row.id, []),
            spec_count=counts.get(row.id, 0),
        )

    return Page(
        items=[one_row(row) for row in rows],
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
