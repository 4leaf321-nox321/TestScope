"""3·5. 계열과 관계 — 무슨 시험이 되나, 누가 만들었나, 어느 부속이 붙나.

`scripts/import_catalog.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from app.modules.accounts.models import User
from app.modules.equipment.models import (
    EquipmentSeries,
    SeriesRelation,
    SpecSource,
)
from app.modules.methods.models import TestMethod
from app.modules.test_items.models import (
    SeriesPendingMethod,
    SeriesTestItem,
    SeriesTestItemMethod,
)
from app.modules.vocabulary.models import (
    VocabularyTerm,
)
from app.shared.text import clean, compare_key
from catalog_import.source import (
    Catalog,
)


def _series_of(
    db: Session,
    obj: dict[str, Any],
    form_factors: dict[str, uuid.UUID],
    drives: dict[str, uuid.UUID],
    makers: dict[str, VocabularyTerm],
    categories: dict[str, VocabularyTerm],
    sources: dict[str, SpecSource],
    actor: User | None,
) -> EquipmentSeries:
    """계열 하나를 없으면 만든다. **있으면 안 덮는다.**"""
    maker = makers.get(obj["manufacturer"])
    name = clean(obj["name"])
    key = compare_key(name)
    found = db.scalar(
        select(EquipmentSeries).where(
            EquipmentSeries.normalized == key,
            EquipmentSeries.maker_term_id.is_(None)
            if maker is None
            else EquipmentSeries.maker_term_id == maker.id,
        )
    )
    if found is not None:
        if obj.get("supplements"):
            _supplement_series(found, obj)
        return found

    first_source = (obj.get("sources") or [{}])[0].get("file")
    found = EquipmentSeries(
        name=name,
        name_ko=obj.get("name_ko"),
        normalized=key,
        maker_term_id=maker.id if maker else None,
        brand=obj.get("brand"),
        category_term_id=(
            categories[obj["category"]].id if obj["category"] in categories else None
        ),
        kind="main" if obj["kind"].startswith("equipment") else obj["kind"],
        drive_term_id=drives.get(obj.get("drive") or ""),
        form_factor_term_id=form_factors.get(obj.get("form_factor") or ""),
        summary=obj.get("description"),
        spec_note=_spec_note(obj),
        source_id=sources[first_source].id if first_source in sources else None,
        created_by_id=actor.id if actor else None,
    )
    db.add(found)
    db.flush()
    return found


def _supplement_series(series: EquipmentSeries, obj: dict[str, Any]) -> None:
    """다른 출처(MaterialTwin)가 같은 계열에 보탠 비고·원문. **한 번만, 덮지 않고.**

    계열 자체는 안 고친다 — 손으로 다듬은 이름·분류가 더 낫다. 보태는 것은 그 출처의
    말(비고)과 원문(raw_limits.materialtwin)뿐이고, 표식이 이미 있으면 안 한다.
    """
    marker = "[MaterialTwin]"
    note = obj.get("notes")
    if isinstance(note, str) and note and marker not in (series.spec_note or ""):
        series.spec_note = f"{series.spec_note}\n{note}" if series.spec_note else note
    raw = obj.get("materialtwin_series")
    if raw:
        limits = dict(series.raw_limits or {})
        if "materialtwin" not in limits:
            limits["materialtwin"] = raw
            series.raw_limits = limits


def _spec_note(obj: dict[str, Any]) -> str | None:
    """사양 칸으로 못 담는 것을 한 덩어리로 남긴다 — 옵션·특징·비고.

    **버리지 않는다.** 지금 담을 칸이 없다는 것과 값이 쓸모없다는 것은 다르다.
    """

    def _one(value: Any) -> str:
        # 원본이 옵션을 `{name, note}` 로도 적는다 — 문자열로 뭉개면 「무엇이 어떻게
        # 달라지나」 가 사라진다(2026-09-10 스키마 개정).
        if isinstance(value, dict):
            head = str(value.get("name") or "")
            tail = str(value.get("note") or "")
            return f"{head} ({tail})" if head and tail else head or tail
        return str(value)

    parts: list[str] = []
    for label, key in (("옵션", "options"), ("특징", "features"), ("비고", "notes")):
        values = obj.get(key)
        if isinstance(values, list) and values:
            parts.append(f"[{label}] " + " · ".join(_one(one) for one in values))
        elif isinstance(values, str) and values:
            parts.append(f"[{label}] {values}")
    return "\n".join(parts) or None


def step_series(
    db: Session,
    cat: Catalog,
    makers: dict[str, VocabularyTerm],
    categories: dict[str, VocabularyTerm],
    items: dict[str, VocabularyTerm],
    methods: dict[str, TestMethod],
    form_factors: dict[str, uuid.UUID],
    drives: dict[str, uuid.UUID],
    actor: User | None,
) -> tuple[dict[str, EquipmentSeries], int, int]:
    """3. 계열과 그 시험 항목. **무슨 시험이 되나는 계열의 성질**이다(ADR 0006).

    돌려주는 것: (계열, 새로 만든 시험 항목 수, 항목 미정으로 남긴 인용 수).
    """
    sources = {row.path: row for row in db.scalars(select(SpecSource))}
    made: dict[str, EquipmentSeries] = {}
    test_items = 0
    pending = 0

    for obj in cat.objects:
        series = _series_of(db, obj, form_factors, drives, makers, categories, sources, actor)
        made[obj["id"]] = series

        # **시험 항목 하나에 시험 항목 하나.** 규격을 걸어 시험 항목을 쪼개지 않는다.
        #
        # 카탈로그의 `test_methods` 는 계열에 붙은 평평한 목록이라, 인장 하나에
        # ASTM D638·ISO 527·ASTM E8 이 함께 걸린다. 그것을 시험 항목 셋으로 만들면
        # **검색이 같은 장비를 여덟 줄로 답한다** — 실제로 그렇게 나왔다.
        #
        # 규격별로 조건이 갈리는 일은 실재하지만, 그것은 사양서가 아니라 그 대를
        # 돌려 본 사람이 아는 것이다. 여기서는 「이 계열은 인장이 된다」 까지만
        # 말하고, 규격은 인용 목록(`spec_note`)으로 남긴다.
        codes = [
            str(code).strip()
            for code in (obj.get("standards") or {}).get("test_methods") or []
            if str(code).strip()
        ]
        linked_codes: set[str] = set()
        for item_id in obj.get("test_items") or []:
            term = items.get(item_id)
            if term is None:
                continue
            by_item = (obj.get("standards") or {}).get("test_methods_by_item") or {}
            listed = set(by_item.get(item_id) or [])
            mine = [
                one
                for one in codes
                if methods.get(one) is not None
                and (one in listed or methods[one].test_item_term_id == term.id)
            ]
            test_item = db.scalar(
                select(SeriesTestItem).where(
                    SeriesTestItem.series_id == series.id,
                    SeriesTestItem.test_item_term_id == term.id,
                )
            )
            if test_item is None:
                test_item = SeriesTestItem(series_id=series.id, test_item_term_id=term.id)
                db.add(test_item)
                db.flush()
                test_items += 1
            # **비고 문자열이 아니라 표로 잇는다.** 글자로 두면 시험법 453건이
            # 아무것도 가리키지 않는 목록으로 남고, 「ASTM D638 되는 장비」 를 물으면
            # 문자열을 훑는 수밖에 없다.
            #
            # 시험 항목이 **이미 있어도** 빠진 링크는 보탠다. 전에는 있는 항목을 통째로
            # 건너뛰어, 나중에 시험 항목이 정해진 규격 115 건이 영영 안 이어졌다 —
            # 두 번째 반입이 첫 반입이 못 한 일을 이어받아야 한다.
            have = {
                one.method_id
                for one in db.scalars(
                    select(SeriesTestItemMethod).where(
                        SeriesTestItemMethod.series_test_item_id == test_item.id
                    )
                )
            }
            for code in mine:
                linked_codes.add(code)
                if methods[code].id not in have:
                    db.add(
                        SeriesTestItemMethod(
                            series_test_item_id=test_item.id, method_id=methods[code].id
                        )
                    )
        # **누가 인용했나를 남긴다.** 시험이 여럿인 계열이 인용한 규격 중 어느 시험의
        # 것인지 모르는 것은 링크를 못 만든다. 그 사실을 DB 에 안 남기면 시험법이
        # 「가능 장비 없음」 으로 서고, 못 하는 시험과 끊긴 연결을 아무도 못 가른다.
        # 시험 항목이 정해지는 순간 `promote_pending` 이 여기서 링크로 올린다.
        for code in codes:
            method = methods.get(code)
            if method is None or code in linked_codes:
                continue
            if method.test_item_term_id is not None:
                # 항목은 정해졌는데 이 계열에 그 시험이 없다 — 온톨로지와 객체가 어긋난
                # 것이라 미정이 아니다. 미정 표에 넣으면 「정하면 붙는다」 가 거짓이 된다.
                continue
            exists = db.scalar(
                select(SeriesPendingMethod).where(
                    SeriesPendingMethod.series_id == series.id,
                    SeriesPendingMethod.method_id == method.id,
                )
            )
            if exists is None:
                db.add(SeriesPendingMethod(series_id=series.id, method_id=method.id))
                pending += 1
        db.flush()
    return made, test_items, pending


def step_relations(db: Session, cat: Catalog, series: dict[str, EquipmentSeries]) -> int:
    """5. 계열끼리의 관계. **부속이 사양값을 바꾼다**(ADR 0006)."""
    made = 0
    for obj in cat.objects:
        host = series[obj["id"]]
        for row in obj.get("relations") or []:
            part = series.get(str(row.get("target")))
            if part is None or part.id == host.id:
                # 온톨로지 노드(시험 항목·규격)를 가리키는 관계는 여기 대상이
                # 아니다 — 그것은 시험 항목으로 이미 들어갔다.
                continue
            exists = db.scalar(
                select(SeriesRelation).where(
                    SeriesRelation.host_series_id == host.id,
                    SeriesRelation.part_series_id == part.id,
                    SeriesRelation.relation == row["type"],
                )
            )
            if exists is not None:
                continue
            db.add(
                SeriesRelation(
                    host_series_id=host.id,
                    part_series_id=part.id,
                    relation=row["type"],
                    note=row.get("note"),
                )
            )
            made += 1
    db.flush()
    return made
