"""기준정보 값의 **쓰임** — 무엇이 이 값을 가리키나, 그리고 그것을 어떻게 떼거나 옮기나.

## 왜 셈이 아니라 목록인가

쓰임 수 「12」 는 「지워도 되나」 에는 답하지만 「그 12 가 무엇인가」 에는 답하지 않는다.
값을 합치거나 폐기하기 전에 사람이 보는 것은 목록이다 — 어느 계열이, 어느 장비가, 어느
규격이 이 값을 쓰는가. 그리고 그 자리에서 **하나씩 뗄 수 있어야** 한다: 「이 계열의
인장은 잘못 붙은 것」 을 고치러 계열 화면까지 가게 하면 안 고친다.

## 한 표에 다 적는다

축마다 **무엇이 가리키나**(모델·칸)와 **그 줄을 어떻게 부르나**(이름·주소), **떼면 어떻게
되나**(줄을 지운다 / 칸을 비운다 / 못 뗀다 — 옮기기만)가 여기 한 표다. 쓰임 수도 같은 표에서
센다 — 세는 표와 보여 주는 표가 다르면 「12 인데 목록엔 10」 이 되고, 그때 사람은 둘 다 안
믿는다.

    delete   연결 줄 자체를 지운다   — 계열의 시험 항목 · 장비의 시험 항목 · 물성 연결
    null     칸을 비운다            — 계열의 제조사 · 시험법의 시험 항목 (비워도 되는 칸)
    none     못 뗀다, 옮기기만       — 장비의 거점 (비울 수 없는 칸)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.modules.equipment.models import (
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
    SpecSource,
)
from app.modules.methods.models import TestMethod
from app.modules.properties.models import TestItemProperty
from app.modules.test_items.models import EquipmentTestItem, SeriesTestItem
from app.modules.vocabulary.models import VocabularyTerm
from app.modules.vocabulary.specs import SpecDefinition, SpecDefinitionCategory

#: (사람이 읽는 이름, 화면 주소) — 주소가 없으면 None.
Described = tuple[str, str | None]
Describer = Callable[[Session, Any], Described]


@dataclass(frozen=True)
class ReferenceKind:
    key: str
    """코드가 거는 이름. 「이 줄을 떼라」 가 이 이름으로 온다."""
    axis: str
    label: str
    """사람이 읽는 묶음 이름 — 「계열의 시험 항목」."""
    model: Any
    column: Any
    detach: str
    """delete · null · none."""
    describe: Describer


def _series(db: Session, series_id: uuid.UUID | None) -> str:
    row = db.get(EquipmentSeries, series_id) if series_id else None
    return row.name if row else "(계열 없음)"


def _equipment(db: Session, equipment_id: uuid.UUID | None) -> tuple[str, str | None]:
    row = db.get(Equipment, equipment_id) if equipment_id else None
    if row is None:
        return "(장비 없음)", None
    return f"{row.asset_no} {row.name}", f"/equipment/{row.id}"


def _term(db: Session, term_id: uuid.UUID | None) -> str:
    row = db.get(VocabularyTerm, term_id) if term_id else None
    return row.value if row else "(값 없음)"


def _describe_series(db: Session, row: EquipmentSeries) -> Described:
    return row.name, f"/catalog/equipment-series/{row.id}"


def _describe_model(db: Session, row: EquipmentModel) -> Described:
    return f"{_series(db, row.series_id)} · {row.name}", f"/catalog/equipment-models/{row.id}"


def _describe_equipment(db: Session, row: Equipment) -> Described:
    return f"{row.asset_no} {row.name}", f"/equipment/{row.id}"


def _describe_method(db: Session, row: TestMethod) -> Described:
    return " ".join(x for x in (row.code, row.edition) if x), f"/methods/{row.id}"


def _describe_series_item(db: Session, row: SeriesTestItem) -> Described:
    return _series(db, row.series_id), f"/catalog/equipment-series/{row.series_id}"


def _describe_equipment_item(db: Session, row: EquipmentTestItem) -> Described:
    return _equipment(db, row.equipment_id)


def _describe_item_property(db: Session, row: TestItemProperty) -> Described:
    return (
        f"{_term(db, row.test_item_term_id)} → {_term(db, row.property_term_id)}",
        "/properties",
    )


def _describe_source(db: Session, row: SpecSource) -> Described:
    return row.title or row.path, None


def _describe_calibration(db: Session, row: EquipmentCalibration) -> Described:
    label, href = _equipment(db, row.equipment_id)
    return f"{label} · {row.calibrated_on.isoformat()}", href


def _describe_definition_category(db: Session, row: SpecDefinitionCategory) -> Described:
    definition = db.get(SpecDefinition, row.definition_id)
    return definition.label if definition else "(사양 정의 없음)", "/spec-definitions"


#: 축마다 무엇이 가리키나. **축을 만들면서 여기 한 줄 더하는 것을 잊으면** 그 축의 값은
#: 영원히 0 으로 보인다 — `tests/api/test_vocabulary_usage.py` 가 잡는다.
REFERENCE_KINDS: tuple[ReferenceKind, ...] = (
    ReferenceKind(
        "equipment_test_item",
        "test_item",
        "장비의 시험 항목",
        EquipmentTestItem,
        EquipmentTestItem.test_item_term_id,
        "delete",
        _describe_equipment_item,
    ),
    ReferenceKind(
        "series_test_item",
        "test_item",
        "계열의 시험 항목",
        SeriesTestItem,
        SeriesTestItem.test_item_term_id,
        "delete",
        _describe_series_item,
    ),
    ReferenceKind(
        "method_test_item",
        "test_item",
        "시험법의 시험 항목",
        TestMethod,
        TestMethod.test_item_term_id,
        "null",
        _describe_method,
    ),
    ReferenceKind(
        "item_property_by_item",
        "test_item",
        "물성 연결",
        TestItemProperty,
        TestItemProperty.test_item_term_id,
        "delete",
        _describe_item_property,
    ),
    ReferenceKind(
        "item_property_by_property",
        "property",
        "시험 항목 연결",
        TestItemProperty,
        TestItemProperty.property_term_id,
        "delete",
        _describe_item_property,
    ),
    ReferenceKind(
        "series_category",
        "equipment_category",
        "계열의 분류",
        EquipmentSeries,
        EquipmentSeries.category_term_id,
        "null",
        _describe_series,
    ),
    ReferenceKind(
        "equipment_category",
        "equipment_category",
        "카탈로그 미연결 장비의 분류",
        Equipment,
        Equipment.category_term_id,
        "none",
        _describe_equipment,
    ),
    ReferenceKind(
        "definition_category",
        "equipment_category",
        "사양 정의의 적용 분류",
        SpecDefinitionCategory,
        SpecDefinitionCategory.category_term_id,
        "delete",
        _describe_definition_category,
    ),
    ReferenceKind(
        "series_maker",
        "manufacturer",
        "계열의 제조사",
        EquipmentSeries,
        EquipmentSeries.maker_term_id,
        "null",
        _describe_series,
    ),
    ReferenceKind(
        "source_maker",
        "manufacturer",
        "사양 출처의 제조사",
        SpecSource,
        SpecSource.maker_term_id,
        "null",
        _describe_source,
    ),
    ReferenceKind(
        "series_form_factor",
        "form_factor",
        "계열의 기종 형태",
        EquipmentSeries,
        EquipmentSeries.form_factor_term_id,
        "null",
        _describe_series,
    ),
    ReferenceKind(
        "model_form_factor",
        "form_factor",
        "기종의 형태",
        EquipmentModel,
        EquipmentModel.form_factor_term_id,
        "null",
        _describe_model,
    ),
    ReferenceKind(
        "series_drive",
        "drive",
        "계열의 구동 방식",
        EquipmentSeries,
        EquipmentSeries.drive_term_id,
        "null",
        _describe_series,
    ),
    ReferenceKind(
        "equipment_site",
        "site",
        "장비의 거점",
        Equipment,
        Equipment.site_term_id,
        "none",
        _describe_equipment,
    ),
    ReferenceKind(
        "calibration_provider",
        "calibration_provider",
        "교정 기록의 기관",
        EquipmentCalibration,
        EquipmentCalibration.provider_term_id,
        "null",
        _describe_calibration,
    ),
    ReferenceKind(
        "method_body",
        "standard_body",
        "시험법의 제정기관",
        TestMethod,
        TestMethod.body_term_id,
        "null",
        _describe_method,
    ),
)

BY_KEY: dict[str, ReferenceKind] = {kind.key: kind for kind in REFERENCE_KINDS}

#: 쓰임 수를 세는 표. **같은 표에서 센다** — 세는 표와 보여 주는 표가 갈리면 「12 인데
#: 목록엔 10」 이 되고, 그때 사람은 둘 다 안 믿는다.
_REFERENCES: dict[str, list[tuple[Any, Any]]] = {}
for _kind in REFERENCE_KINDS:
    _REFERENCES.setdefault(_kind.axis, []).append((_kind.model, _kind.column))
