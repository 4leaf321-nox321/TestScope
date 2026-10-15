"""**대체된 규격을 아직 가리키는 곳** — 신뢰성 시험의 근거 규격 · 장비 시험 항목의 규격.

규격의 판이 바뀌면 옛 판은 지우지 않고 `superseded` 로 둔다(옛 판으로 잰 데이터가 있다). 그런데
그 옛 판을 근거로 적어 둔 신뢰성 시험과 장비 시험 항목은 **아무도 모르게 옛 판에 머물렀다** —
알림도 남은 일도 없었다(2026-10-16). 판이 바뀌었다는 사실 하나로 그 시험의 조건 · 판정이
달라질 수 있는데, 그것을 볼 사람에게 닿는 길이 없었다.

**계산이지 기록이 아니다.** 「대체됨」 상태의 규격을 가리키는 줄을 그때그때 센다 — 새 판으로
고치면 목록에서 저절로 빠진다. 사건을 따로 적으면 고친 뒤에도 남아 지우는 일이 하나 더 생긴다.

범위는 둘이다:

- **신뢰성 시험** — 최신판 · 안 지운 시험의 지금 값(`is_current`) 중 규격 참조
  (`ref_method_id`).
  사업부로 묶는다(시험이 사업부의 것이다).
- **장비 시험 항목** — 폐기 안 된 장비의 시험 항목이 가리키는 규격(`method_id`). 장비를 가진
  부서로 묶는다.
"""

from __future__ import annotations

import uuid
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.equipment.models import Equipment
from app.modules.methods.models import TestMethod
from app.modules.methods.schemas import SupersededRefOut
from app.modules.reliability.models import ReliabilityTest
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import VocabularyTerm
from app.modules.workspaces.models import Workspace


def _label(method: TestMethod | None) -> str:
    if method is None:
        return ""
    return f"{method.code} {method.edition or ''}".strip()


def superseded_refs(
    db: Session,
    *,
    divisions: set[uuid.UUID] | None = None,
    workspaces: set[uuid.UUID] | None = None,
) -> list[SupersededRefOut]:
    """대체된 규격을 가리키는 줄. 둘 다 `None` 이면 전부(시스템 관리자), 아니면 그 사업부의
    신뢰성 시험과 그 부서의 장비만."""
    everything = divisions is None and workspaces is None
    out: list[SupersededRefOut] = []
    successors: dict[uuid.UUID, TestMethod | None] = {}

    def successor(method: TestMethod) -> TestMethod | None:
        if method.superseded_by_id is None:
            return None
        if method.superseded_by_id not in successors:
            successors[method.superseded_by_id] = db.get(TestMethod, method.superseded_by_id)
        return successors[method.superseded_by_id]

    if everything or divisions:
        stmt = (
            select(AttributeValue, AttributeDefinition, ReliabilityTest, TestMethod)
            .join(AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id)
            .join(ReliabilityTest, ReliabilityTest.id == AttributeValue.reliability_test_id)
            .join(TestMethod, TestMethod.id == AttributeValue.ref_method_id)
            .where(
                AttributeValue.is_current.is_(True),
                ReliabilityTest.deleted_at.is_(None),
                ReliabilityTest.superseded_by_id.is_(None),
                TestMethod.status == "superseded",
                TestMethod.deleted_at.is_(None),
            )
        )
        if not everything:
            stmt = stmt.where(ReliabilityTest.division_term_id.in_(divisions or set()))
        rows = db.execute(stmt.order_by(TestMethod.code, ReliabilityTest.name)).all()
        names = {
            term.id: term
            for term in db.scalars(
                select(VocabularyTerm).where(
                    VocabularyTerm.id.in_({test.division_term_id for _, _, test, _ in rows})
                )
            )
        }
        for _value, definition, test, method in rows:
            division = names.get(test.division_term_id)
            code = (division.code or "") if division else ""
            after = successor(method)
            out.append(
                SupersededRefOut(
                    kind="reliability_test",
                    target_id=test.id,
                    target_label=test.name,
                    owner=division.value if division else None,
                    owner_id=test.division_term_id,
                    detail=definition.label,
                    # 사업부 화면을 그 시험 이름으로 좁혀 연다 — 보기 · 수정이 그 화면에 있다.
                    link=(
                        f"/reliability-tests/{code}?name={quote(test.name)}"
                        if code
                        else "/reliability-tests"
                    ),
                    method_id=method.id,
                    method_label=_label(method),
                    successor_id=after.id if after else None,
                    successor_label=_label(after) or None,
                )
            )

    if everything or workspaces:
        equipment_stmt = (
            select(EquipmentTestItem, Equipment, TestMethod, VocabularyTerm)
            .join(Equipment, Equipment.id == EquipmentTestItem.equipment_id)
            .join(TestMethod, TestMethod.id == EquipmentTestItem.method_id)
            .join(VocabularyTerm, VocabularyTerm.id == EquipmentTestItem.test_item_term_id)
            .where(
                Equipment.deleted_at.is_(None),
                Equipment.status != "retired",
                TestMethod.status == "superseded",
                TestMethod.deleted_at.is_(None),
            )
        )
        if not everything:
            equipment_stmt = equipment_stmt.where(
                Equipment.owner_workspace_id.in_(workspaces or set())
            )
        found = db.execute(equipment_stmt.order_by(TestMethod.code, Equipment.asset_no)).all()
        owners = {
            row.id: row
            for row in db.scalars(
                select(Workspace).where(
                    Workspace.id.in_({one.owner_workspace_id for _, one, _, _ in found})
                )
            )
        }
        for _item, equipment, method, term in found:
            owner = owners.get(equipment.owner_workspace_id)
            after = successor(method)
            out.append(
                SupersededRefOut(
                    kind="equipment",
                    target_id=equipment.id,
                    target_label=f"{equipment.asset_no} {equipment.name}",
                    owner=owner.name if owner else None,
                    owner_id=equipment.owner_workspace_id,
                    detail=term.value,
                    link=f"/equipment/{equipment.id}",
                    method_id=method.id,
                    method_label=_label(method),
                    successor_id=after.id if after else None,
                    successor_label=_label(after) or None,
                )
            )
    return out
