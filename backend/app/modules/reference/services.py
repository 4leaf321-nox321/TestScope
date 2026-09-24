"""온톨로지 허브 — **객체 종류마다 무슨 칸이 있고, 어떤 칸을 관리자가 더할 수 있나를 한 표로.**

전에는 흩어져 있었다: 기종의 칸은 「장비 기종 사양」, 신뢰성 시험의 칸은 「신뢰성 시험 속성」,
축의 칸은 「온톨로지 편집 → 축」. 계열·규격은 관리자가 칸을 못 더했다. 그래서 「이 시스템의
온톨로지가 무엇인가」 를 물으면 답할 화면이 없었다 — 이름 사전만 「온톨로지」 라고 불려서
객체는 온톨로지가 아닌 것처럼 읽혔다(ReportArchive 는 객체 종류·속성 정의·별칭·관계를 한
체계로 둔다).

저장은 그대로다 — 사슬의 뼈대(계열·기종·규격·보유 장비)는 자기 표, 이름은 축의 값. 판정
(사양 → 조건 축 → 장비)이 FK 로 타야 빠르기 때문. 바뀐 것은 **관리 화면이 한 체계로 보이는
것**이다: 모든 종류에 등록·목록·정의 화면이 있고, 정의는 대상마다 같은 얼개(속성 정의)다.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeDefinition
from app.modules.equipment.models import Equipment, EquipmentModel, EquipmentSeries
from app.modules.methods.models import TestMethod
from app.modules.reference.schemas import ObjectKindOut
from app.modules.reliability.models import ReliabilityTest
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.modules.vocabulary.specs import SpecDefinition
from app.modules.workspaces.models import Workspace


@dataclass(frozen=True)
class _Kind:
    key: str
    label: str
    layer: str
    fixed_fields: tuple[str, ...]
    list_path: str
    note: str
    attribute_target: str | None = None
    """속성 정의의 대상 키 — 있으면 관리자가 속성을 더한다."""


#: 자기 표를 가진 객체 종류. 고정 칸은 그 표의 열 중 사람이 보는 것.
_TABLE_KINDS: tuple[_Kind, ...] = (
    _Kind(
        "series",
        "장비 계열",
        "catalog",
        (
            "이름",
            "제조사",
            "분류",
            "종류",
            "구동",
            "형태",
            "상태",
            "소개",
            "수행 가능 시험 항목",
            "인용 규격",
            "계열 관계",
        ),
        "/catalog/equipment-series",
        "제조사 제품군. 수행 가능 시험의 정의 단위. 시스템 관리자 · 반입.",
        attribute_target="series",
    ),
    _Kind(
        "model",
        "장비 기종",
        "catalog",
        ("이름", "계열", "사양 값", "기종 고유 사양", "원문 사양"),
        "/catalog/equipment-models",
        "수치 사양의 저장 단위. 보유 장비가 가리키는 대상. 시스템 관리자 · 반입.",
    ),
    _Kind(
        "method",
        "시험법 / 규격",
        "catalog",
        ("코드", "판", "제목", "소속 시험 항목", "제정기관", "상태", "후속 판", "요구 조건"),
        "/methods",
        "규격 문서. 시험 항목에 소속되고 계열이 인용한다. 시스템 관리자 · 반입.",
        attribute_target="method",
    ),
    _Kind(
        "equipment",
        "보유 장비",
        "operations",
        (
            "자산번호",
            "장비명",
            "분류(중분류 = 군 · 소분류 = 유형)",
            "기종",
            "보유 부서",
            "거점(건물)",
            "설치 위치",
            "담당자",
            "공용 여부",
            "상태",
            "도입일",
            "교정",
            "수행 시험 항목",
        ),
        "/equipment",
        "우리가 가진 실물. 부서 관리자가 등록.",
        attribute_target="equipment",
    ),
    _Kind(
        "reliability_test",
        "신뢰성 시험",
        "operations",
        ("부서", "이름", "목적", "구성 시험 항목"),
        "/reliability-tests",
        "부서가 수행하는 절차. 부서 관리자가 등록.",
        attribute_target="reliability_test",
    ),
    _Kind(
        "workspace",
        "부서",
        "operations",
        ("주소", "이름", "상위 부서", "순서", "보관 상태", "장비 가시성", "메뉴 표시"),
        "/admin/workspaces",
        "조직도. 장비의 소유 단위이자 권한 단위. 시스템 관리자.",
    ),
)

#: 온톨로지 축 중 자기 화면을 가진 축의 목록 주소 — 나머지는 이름 사전 화면으로.
_AXIS_PATHS = {
    "test_item": "/catalog/test-items",
    "property": "/properties",
}
_AXIS_NOTES = {
    "test_item": "장비가 할 수 있는 측정. 사슬의 허브 — 물성·규격·계열·보유 장비가 가리킨다.",
    "property": "시험으로 얻는 물성. 물성 기준 검색의 출발점.",
    "equipment_category": "장비 분류 — 군 → 유형 트리.",
    "manufacturer": "제조사.",
    "site": "거점(사업장·동).",
    "standard_body": "규격 제정기관.",
}


def _count(db: Session, stmt: Select[tuple[int]]) -> int:
    return int(db.scalar(stmt) or 0)


def overview(db: Session) -> list[ObjectKindOut]:
    attribute_counts: dict[tuple[str, str], int] = {}
    for target, status, n in db.execute(
        select(AttributeDefinition.target, AttributeDefinition.status, func.count())
        .where(AttributeDefinition.is_active.is_(True))
        .group_by(AttributeDefinition.target, AttributeDefinition.status)
    ):
        attribute_counts[(target, status)] = int(n)

    counts = {
        "series": _count(
            db,
            select(func.count())
            .select_from(EquipmentSeries)
            .where(EquipmentSeries.deleted_at.is_(None)),
        ),
        "model": _count(
            db,
            select(func.count())
            .select_from(EquipmentModel)
            .where(EquipmentModel.deleted_at.is_(None)),
        ),
        "method": _count(
            db,
            select(func.count())
            .select_from(TestMethod)
            .where(TestMethod.deleted_at.is_(None)),
        ),
        "equipment": _count(
            db,
            select(func.count()).select_from(Equipment).where(Equipment.deleted_at.is_(None)),
        ),
        "reliability_test": _count(
            db,
            select(func.count())
            .select_from(ReliabilityTest)
            .where(ReliabilityTest.deleted_at.is_(None)),
        ),
        "workspace": _count(
            db,
            select(func.count()).select_from(Workspace).where(Workspace.is_active.is_(True)),
        ),
    }
    spec_count = _count(
        db, select(func.count()).select_from(SpecDefinition).where(SpecDefinition.is_active)
    )
    condition_count = _count(
        db, select(func.count()).select_from(ConditionKey).where(ConditionKey.is_active)
    )

    out: list[ObjectKindOut] = []
    for kind in _TABLE_KINDS:
        if kind.attribute_target:
            defined_kind = "속성"
            defined = attribute_counts.get((kind.attribute_target, "standard"), 0)
            drafts = attribute_counts.get((kind.attribute_target, "draft"), 0)
            define_path = {
                "series": "/attribute-definitions/equipment-series",
                "method": "/attribute-definitions/method",
                "equipment": "/attribute-definitions/equipment",
                "reliability_test": "/attribute-definitions/reliability-test",
            }[kind.attribute_target]
        elif kind.key == "model":
            defined_kind, defined, drafts, define_path = (
                "사양",
                spec_count,
                0,
                "/spec-definitions",
            )
        else:
            defined_kind, defined, drafts, define_path = None, 0, 0, None
        out.append(
            ObjectKindOut(
                key=kind.key,
                label=kind.label,
                layer=kind.layer,
                storage="table",
                count=counts[kind.key],
                fixed_fields=list(kind.fixed_fields),
                defined_kind=defined_kind,
                defined_count=defined,
                draft_count=drafts,
                list_path=kind.list_path,
                define_path=define_path,
                note=kind.note,
            )
        )

    term_counts = {
        vocabulary_id: int(n)
        for vocabulary_id, n in db.execute(
            select(VocabularyTerm.vocabulary_id, func.count())
            .where(VocabularyTerm.status == "active")
            .group_by(VocabularyTerm.vocabulary_id)
        )
    }
    for axis in db.scalars(select(Vocabulary).order_by(Vocabulary.slug)):
        schema = list(axis.attribute_schema or [])
        if axis.slug == "test_item":
            defined_kind, defined, define_path = (
                "검색 조건",
                condition_count,
                "/conditions",
            )
        elif schema:
            # 값의 칸은 허브의 축 판(「축 고치기」)에서 고친다 — 따로 가는 문이 없다.
            defined_kind, defined, define_path = "값의 칸", len(schema), None
        else:
            defined_kind, defined, define_path = None, 0, None
        out.append(
            ObjectKindOut(
                key=f"axis:{axis.slug}",
                label=axis.label,
                layer="vocabulary",
                storage="vocabulary",
                count=term_counts.get(axis.id, 0),
                fixed_fields=["이름", "코드", "별칭", "상위 값"]
                + [str(one.get("label") or one.get("key")) for one in schema],
                defined_kind=defined_kind,
                defined_count=defined,
                draft_count=0,
                list_path=_AXIS_PATHS.get(axis.slug, f"/reference?kind=axis:{axis.slug}"),
                define_path=define_path,
                note=_AXIS_NOTES.get(axis.slug, axis.description or "이름 사전의 축."),
            )
        )
    return out
