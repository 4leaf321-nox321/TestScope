"""지식 그래프의 **정의** — 무엇이 노드이고 무엇이 선인가.

StandardPlatform 은 객체 종류와 관계 종류를 표(온톨로지)로 갖고 그래프가 그것을 읽는다.
TestScope 는 사슬의 뼈대가 자기 표(계열·기종·규격·보유 장비 …)라 관계가 **FK 와 연결 표**에
박혀 있다. 그래서 정의를 여기 코드로 적는다 — 노드 종류 하나가 `NodeType`, 선 종류 하나가
`EdgeKind`(어느 표의 어느 두 열이 어느 두 종류를 잇나). 그래프 엔진(`engine.py`)은 이 목록만
읽는다: 새 관계가 생기면 여기 한 줄이다.

노드 id 는 `"<종류>:<uuid>"` — 표가 다르면 uuid 만으로는 종류를 모른다(계열과 기종이 같은
uuid 를 쓸 일은 없지만, id 를 보고 어느 화면으로 갈지 정해야 한다).

## 무엇이 선인가

관계도 HTML(2026-09-16)의 ①~⑬ 이 그대로다: 측정 물성 · 조회 조건 축 · 규격의 소속 시험
항목 · 규격 요구 조건 · 수행 가능 시험 항목 · 인용 규격 · 구성 기종 · 계열 간 관계 ·
지정 기종 · 수행 시험 항목 · 소유 부서 · 수행 부서 · 구성 시험 항목. 거기에 제조사·분류·
거점·제정기관·후속 판·상위 분류·상위 부서, 그리고 정식 속성이 가리키는 규격·기준정보 값.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, select

from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    SeriesRelation,
)
from app.modules.methods.models import MethodRequirement, TestMethod, TestMethodItem
from app.modules.properties.models import TestItemProperty
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.test_items.models import (
    EquipmentTestItem,
    SeriesPendingMethod,
    SeriesTestItem,
    SeriesTestItemMethod,
    TestItemConditionKey,
)
from app.modules.vocabulary.models import VocabularyTerm
from app.modules.workspaces.models import Workspace


@dataclass(frozen=True)
class NodeType:
    slug: str
    label: str
    layer: str
    """catalog · vocabulary · operations — 색 묶음과 설명에 쓴다."""
    icon: str
    axis: str | None = None
    """기준정보 축의 값이면 그 축 slug. 아니면 None(자기 표)."""
    detail_path: str | None = None
    """상세 화면 주소 서식 — `{id}` 가 uuid."""
    sort_order: int = 0


NODE_TYPES: tuple[NodeType, ...] = (
    NodeType(
        "test_item",
        "시험 항목",
        "vocabulary",
        "list-checks",
        "test_item",
        "/catalog/test-items/{id}",
        10,
    ),
    NodeType("property", "물성 항목", "vocabulary", "atom", "property", "/properties", 20),
    NodeType("condition_key", "검색 조건", "vocabulary", "ruler", None, "/conditions", 30),
    NodeType("method", "시험법 / 규격", "catalog", "scroll-text", None, "/methods/{id}", 40),
    NodeType(
        "series", "장비 계열", "catalog", "boxes", None, "/catalog/equipment-series/{id}", 50
    ),
    NodeType(
        "model", "장비 기종", "catalog", "package", None, "/catalog/equipment-models/{id}", 60
    ),
    NodeType("manufacturer", "제조사", "vocabulary", "factory", "manufacturer", None, 70),
    NodeType(
        "equipment_category", "장비 분류", "vocabulary", "tags", "equipment_category", None, 80
    ),
    NodeType(
        "standard_body", "규격 제정기관", "vocabulary", "landmark", "standard_body", None, 90
    ),
    NodeType("equipment", "보유 장비", "operations", "wrench", None, "/equipment/{id}", 100),
    NodeType("reliability_test", "신뢰성 시험", "operations", "gauge", None, None, 110),
    NodeType("workspace", "부서", "operations", "building-2", None, None, 120),
    NodeType("site", "거점", "vocabulary", "map-pin", "site", None, 130),
)
NODE_TYPE_BY_SLUG: dict[str, NodeType] = {one.slug: one for one in NODE_TYPES}


@dataclass(frozen=True)
class EdgeKind:
    """선 종류 하나 — 어느 표의 어느 두 열이 (src 종류 → dst 종류)를 잇나."""

    slug: str
    label: str
    inverse_label: str
    src_type: str
    dst_type: str
    stmt: Select[Any]
    """(src_uuid, dst_uuid, row_id) 세 열을 내는 select. 엔진이 여기에 where 를 더한다."""
    src_col: ColumnElement[uuid.UUID]
    dst_col: ColumnElement[uuid.UUID]
    directed: bool = True
    note: str = ""


def _kind(
    slug: str,
    label: str,
    inverse: str,
    src_type: str,
    dst_type: str,
    src_col: Any,
    dst_col: Any,
    row_id: Any,
    *,
    base: Select[Any] | None = None,
    directed: bool = True,
    note: str = "",
) -> EdgeKind:
    stmt = (base if base is not None else select(src_col, dst_col, row_id)).where(
        src_col.is_not(None), dst_col.is_not(None)
    )
    return EdgeKind(
        slug, label, inverse, src_type, dst_type, stmt, src_col, dst_col, directed, note
    )


#: 계열 간 관계의 이름 — 코드 값을 사람 말로.
SERIES_RELATION_LABELS: dict[str, tuple[str, str]] = {
    "compatible_accessory": ("호환 부속", "부속의 본체"),
    "fits_on": ("장착 대상", "장착 부속"),
    "requires": ("필요 부속", "필요로 하는 계열"),
    "controlled_by": ("제어 장치", "제어 대상"),
    "extends_temperature": ("온도 범위 확장", "온도 확장 부속"),
    "simulates_environment": ("환경 모사", "환경 모사 부속"),
    "successor_of": ("이전 계열", "후속 계열"),
    "same_family_as": ("같은 제품군", "같은 제품군"),
    "variant_of": ("원형 계열", "변형 계열"),
}


def _series_relation_kinds() -> list[EdgeKind]:
    out: list[EdgeKind] = []
    for relation, (label, inverse) in SERIES_RELATION_LABELS.items():
        out.append(
            _kind(
                f"series:{relation}",
                label,
                inverse,
                "series",
                "series",
                SeriesRelation.part_series_id
                if relation != "successor_of"
                else SeriesRelation.host_series_id,
                SeriesRelation.host_series_id
                if relation != "successor_of"
                else SeriesRelation.part_series_id,
                SeriesRelation.id,
                base=select(
                    SeriesRelation.part_series_id
                    if relation != "successor_of"
                    else SeriesRelation.host_series_id,
                    SeriesRelation.host_series_id
                    if relation != "successor_of"
                    else SeriesRelation.part_series_id,
                    SeriesRelation.id,
                ).where(SeriesRelation.relation == relation),
                directed=relation != "same_family_as",
            )
        )
    return out


#: 정식 속성이 가리키는 규격·기준정보 값 — 「근거 규격」 같은 속성이 선이 된다.
_ATTRIBUTE_TARGETS: dict[str, tuple[str, Any]] = {
    "reliability_test": ("reliability_test", AttributeValue.reliability_test_id),
    "equipment": ("equipment", AttributeValue.equipment_id),
    "series": ("series", AttributeValue.series_id),
    "method": ("method", AttributeValue.method_id),
}


def _attribute_kinds() -> list[EdgeKind]:
    out: list[EdgeKind] = []
    for target, (node_type, column) in _ATTRIBUTE_TARGETS.items():
        base_where = [
            AttributeDefinition.target == target,
            AttributeDefinition.status == "standard",
            AttributeDefinition.is_active.is_(True),
        ]
        out.append(
            _kind(
                f"attribute_method:{target}",
                "속성이 가리키는 규격",
                "이 규격을 속성으로 적은 것",
                node_type,
                "method",
                column,
                AttributeValue.ref_method_id,
                AttributeValue.id,
                base=select(column, AttributeValue.ref_method_id, AttributeValue.id)
                .join(
                    AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id
                )
                .where(*base_where, AttributeDefinition.kind == "method"),
            )
        )
        out.append(
            _kind(
                f"attribute_term:{target}",
                "속성이 가리키는 기준정보 값",
                "이 값을 속성으로 적은 것",
                node_type,
                "term",
                column,
                AttributeValue.term_id,
                AttributeValue.id,
                base=select(column, AttributeValue.term_id, AttributeValue.id)
                .join(
                    AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id
                )
                .where(*base_where, AttributeDefinition.kind == "term"),
            )
        )
    return out


EDGE_KINDS: tuple[EdgeKind, ...] = (
    # ① 물성 ⇄ 시험 항목
    _kind(
        "measures",
        "측정 물성",
        "측정 시험",
        "test_item",
        "property",
        TestItemProperty.test_item_term_id,
        TestItemProperty.property_term_id,
        TestItemProperty.id,
        note="제안(suggested)·확인(confirmed) 둘 다 — 상태는 카탈로그 화면이 가른다",
    ),
    # ② 시험 항목 → 검색 조건 축
    _kind(
        "asks",
        "조회 조건 축",
        "조건을 묻는 시험",
        "test_item",
        "condition_key",
        TestItemConditionKey.test_item_term_id,
        TestItemConditionKey.condition_key_id,
        TestItemConditionKey.id,
    ),
    # ③ 규격 → 시험 항목
    _kind(
        "belongs_to",
        "소속 시험 항목",
        "규격",
        "method",
        "test_item",
        TestMethodItem.method_id,
        TestMethodItem.test_item_term_id,
        TestMethodItem.id,
        # N:M 이라 간선이 규격마다 여럿일 수 있다 — 짝 표에서 바로 읽는다.
        base=select(
            TestMethodItem.method_id, TestMethodItem.test_item_term_id, TestMethodItem.id
        )
        .join(TestMethod, TestMethod.id == TestMethodItem.method_id)
        .where(TestMethod.deleted_at.is_(None)),
    ),
    # ④ 규격 → 검색 조건 축 (요구 조건)
    _kind(
        "requires_condition",
        "요구 조건",
        "요구하는 규격",
        "method",
        "condition_key",
        MethodRequirement.method_id,
        MethodRequirement.condition_key_id,
        MethodRequirement.id,
    ),
    # 규격 → 제정기관
    _kind(
        "issued_by",
        "제정기관",
        "제정 규격",
        "method",
        "standard_body",
        TestMethod.id,
        TestMethod.body_term_id,
        TestMethod.id,
        base=select(TestMethod.id, TestMethod.body_term_id, TestMethod.id).where(
            TestMethod.deleted_at.is_(None)
        ),
    ),
    # 규격 → 후속 판
    _kind(
        "superseded_by",
        "후속 판",
        "이전 판",
        "method",
        "method",
        TestMethod.id,
        TestMethod.superseded_by_id,
        TestMethod.id,
        base=select(TestMethod.id, TestMethod.superseded_by_id, TestMethod.id).where(
            TestMethod.deleted_at.is_(None)
        ),
    ),
    # ⑤ 계열 → 시험 항목
    _kind(
        "performs",
        "수행 가능 시험 항목",
        "수행 가능 계열",
        "series",
        "test_item",
        SeriesTestItem.series_id,
        SeriesTestItem.test_item_term_id,
        SeriesTestItem.id,
    ),
    # 계열 → 규격 (인용, 시험 항목에 붙은 것)
    _kind(
        "cites",
        "인용 규격",
        "인용 계열",
        "series",
        "method",
        SeriesTestItem.series_id,
        SeriesTestItemMethod.method_id,
        SeriesTestItemMethod.id,
        base=select(
            SeriesTestItem.series_id, SeriesTestItemMethod.method_id, SeriesTestItemMethod.id
        ).join(SeriesTestItem, SeriesTestItem.id == SeriesTestItemMethod.series_test_item_id),
    ),
    # 계열 → 규격 (인용, 시험 항목 미지정)
    _kind(
        "cites_pending",
        "인용 규격 (시험 항목 미지정)",
        "인용 계열",
        "series",
        "method",
        SeriesPendingMethod.series_id,
        SeriesPendingMethod.method_id,
        SeriesPendingMethod.id,
    ),
    # ⑥ 계열 → 기종
    _kind(
        "has_model",
        "구성 기종",
        "계열",
        "series",
        "model",
        EquipmentModel.series_id,
        EquipmentModel.id,
        EquipmentModel.id,
        base=select(EquipmentModel.series_id, EquipmentModel.id, EquipmentModel.id).where(
            EquipmentModel.deleted_at.is_(None)
        ),
    ),
    # 계열 → 제조사 · 분류
    _kind(
        "made_by",
        "제조사",
        "제조 계열",
        "series",
        "manufacturer",
        EquipmentSeries.id,
        EquipmentSeries.maker_term_id,
        EquipmentSeries.id,
        base=select(
            EquipmentSeries.id, EquipmentSeries.maker_term_id, EquipmentSeries.id
        ).where(EquipmentSeries.deleted_at.is_(None)),
    ),
    _kind(
        "classified_as",
        "분류",
        "이 분류의 계열",
        "series",
        "equipment_category",
        EquipmentSeries.id,
        EquipmentSeries.category_term_id,
        EquipmentSeries.id,
        base=select(
            EquipmentSeries.id, EquipmentSeries.category_term_id, EquipmentSeries.id
        ).where(EquipmentSeries.deleted_at.is_(None)),
    ),
    # 분류 트리
    _kind(
        "category_parent",
        "상위 분류",
        "하위 분류",
        "equipment_category",
        "equipment_category",
        VocabularyTerm.id,
        VocabularyTerm.parent_term_id,
        VocabularyTerm.id,
        base=select(VocabularyTerm.id, VocabularyTerm.parent_term_id, VocabularyTerm.id).where(
            VocabularyTerm.status == "active"
        ),
    ),
    # ⑨ 보유 장비 → 기종
    _kind(
        "instance_of",
        "지정 기종",
        "보유 장비",
        "equipment",
        "model",
        Equipment.id,
        Equipment.model_id,
        Equipment.id,
        base=select(Equipment.id, Equipment.model_id, Equipment.id).where(
            Equipment.deleted_at.is_(None)
        ),
    ),
    # ⑩ 보유 장비 → 시험 항목
    _kind(
        "performs_item",
        "수행 시험 항목",
        "수행 장비",
        "equipment",
        "test_item",
        EquipmentTestItem.equipment_id,
        EquipmentTestItem.test_item_term_id,
        EquipmentTestItem.id,
    ),
    # ⑪ 보유 장비 → 부서 · 거점
    _kind(
        "owned_by",
        "소유 부서",
        "보유 장비",
        "equipment",
        "workspace",
        Equipment.id,
        Equipment.owner_workspace_id,
        Equipment.id,
        base=select(Equipment.id, Equipment.owner_workspace_id, Equipment.id).where(
            Equipment.deleted_at.is_(None)
        ),
    ),
    _kind(
        "located_at",
        "거점",
        "거점의 장비",
        "equipment",
        "site",
        Equipment.id,
        Equipment.site_term_id,
        Equipment.id,
        base=select(Equipment.id, Equipment.site_term_id, Equipment.id).where(
            Equipment.deleted_at.is_(None)
        ),
    ),
    # ⑫ 신뢰성 시험 → 부서, ⑬ → 시험 항목
    _kind(
        "run_by",
        "수행 부서",
        "수행 신뢰성 시험",
        "reliability_test",
        "workspace",
        ReliabilityTest.id,
        ReliabilityTest.workspace_id,
        ReliabilityTest.id,
        base=select(
            ReliabilityTest.id, ReliabilityTest.workspace_id, ReliabilityTest.id
        ).where(ReliabilityTest.deleted_at.is_(None)),
    ),
    _kind(
        "uses_item",
        "구성 시험 항목",
        "쓰는 신뢰성 시험",
        "reliability_test",
        "test_item",
        ReliabilityTestItem.reliability_test_id,
        ReliabilityTestItem.test_item_term_id,
        ReliabilityTestItem.id,
    ),
    # 부서 트리
    _kind(
        "workspace_parent",
        "상위 부서",
        "하위 부서",
        "workspace",
        "workspace",
        Workspace.id,
        Workspace.parent_id,
        Workspace.id,
        base=select(Workspace.id, Workspace.parent_id, Workspace.id).where(
            Workspace.is_active.is_(True)
        ),
    ),
    *_series_relation_kinds(),
    *_attribute_kinds(),
)
EDGE_KIND_BY_SLUG: dict[str, EdgeKind] = {one.slug: one for one in EDGE_KINDS}

#: 값(term) 을 가리키는 속성 선의 dst 는 축을 모른다 — 엔진이 값의 축으로 종류를 정한다.
TERM_TYPE_BY_AXIS: dict[str, str] = {
    one.axis: one.slug for one in NODE_TYPES if one.axis is not None
}


def node_id(type_slug: str, row_id: uuid.UUID) -> str:
    return f"{type_slug}:{row_id}"


def split_node_id(raw: str) -> tuple[str, uuid.UUID] | None:
    type_slug, _, tail = raw.partition(":")
    if type_slug not in NODE_TYPE_BY_SLUG:
        return None
    try:
        return type_slug, uuid.UUID(tail)
    except ValueError:
        return None


#: 아직 안 이어졌어도 정의로 그리는 (종류, 종류) 쌍은 EDGE_KINDS 그 자체다 — 구조 그림은
#: 관계 수 0 을 점선으로 그린다.
