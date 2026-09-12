"""장비 카탈로그 — 계열과 기종, 그리고 사양서상 시험 항목.

보유 장비(`services.py`)와 나눈 이유는 ADR 0004 에 있다. 여기는 **제조사가 파는 것**
이고, 저기는 **우리가 가진 것**이다.

카탈로그가 다시 두 층인 이유는 ADR 0006 이다.

    계열(EquipmentSeries)   무슨 시험이 되나 · 어느 부속이 붙나 · 누가 만들었나
    기종(EquipmentModel)    수치가 갈리는 자리. 보유 장비가 가리키는 것

## 전사 공용이라 시스템 관리자만 고친다

한 부서가 계열의 분류나 사양을 고치면, 다른 부서가 가리키던 그 기종의 뜻이 바뀐다.
보유 장비가 소유 부서의 관리자 몫인 것과 다른 축이다.

## 문은 하나다

2026-09-13 에 1,474줄을 셋으로 갈랐다 — `catalog_common`(공통 조각·거르기) ·
`catalog_series`(계열) · `catalog_models`(기종). 부르는 쪽(라우터·services·시드)은 전부
`catalog.<이름>` 으로 쓰므로 여기서 그 이름들을 그대로 다시 내보낸다. 새 함수는 세 모듈
중 하나에 적고 여기 `__all__` 에 한 줄 더한다.
"""

from __future__ import annotations

from app.modules.equipment.catalog_common import (
    CATALOG_STATUS_LABEL,
    KIND_LABEL,
    _cited_methods,
    _counted,
    _limits,
    _model_counts,
    _options,
    _relations,
    _term_value,
    _term_values,
    _test_item_names,
    _test_items,
    _unit_counts,
    get_model,
    get_series,
    model_filter_options,
    series_filter_options,
)
from app.modules.equipment.catalog_models import (
    HEADLINE_FALLBACK,
    HEADLINE_MAX,
    _headline_specs,
    _series_of,
    _spec_counts,
    create_model,
    delete_model,
    list_models,
    list_sources,
    model_out,
    update_model,
)
from app.modules.equipment.catalog_series import (
    _method_id,
    _pending_methods,
    _resolved,
    _series_units,
    add_relation,
    add_test_item,
    copy_test_items_to,
    create_series,
    delete_limit,
    delete_relation,
    delete_series,
    delete_test_item,
    list_series,
    series_out,
    update_series,
    upsert_limit,
)

__all__ = [
    "CATALOG_STATUS_LABEL",
    "HEADLINE_FALLBACK",
    "HEADLINE_MAX",
    "KIND_LABEL",
    "_cited_methods",
    "_counted",
    "_headline_specs",
    "_limits",
    "_method_id",
    "_model_counts",
    "_options",
    "_pending_methods",
    "_relations",
    "_resolved",
    "_series_of",
    "_series_units",
    "_spec_counts",
    "_term_value",
    "_term_values",
    "_test_item_names",
    "_test_items",
    "_unit_counts",
    "add_relation",
    "add_test_item",
    "copy_test_items_to",
    "create_model",
    "create_series",
    "delete_limit",
    "delete_model",
    "delete_relation",
    "delete_series",
    "delete_test_item",
    "get_model",
    "get_series",
    "list_models",
    "list_series",
    "list_sources",
    "model_filter_options",
    "model_out",
    "series_filter_options",
    "series_out",
    "update_model",
    "update_series",
    "upsert_limit",
]
