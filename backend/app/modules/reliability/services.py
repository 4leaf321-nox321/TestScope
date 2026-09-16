"""신뢰성 시험 — 읽기는 로그인한 누구나, 쓰기는 그 부서의 관리자와 시스템 관리자."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes import services as attributes
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.equipment.models import Equipment
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import ReliabilityTestItemOut, ReliabilityTestOut
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.permissions import (
    membership_of,
    require_manager,
    visible_equipment_ids,
    workspace_by_slug,
)


def _can_edit(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_system_admin:
        return True
    membership = membership_of(db, workspace_id=workspace_id, user_id=user.id)
    return membership is not None and membership.role == "manager"


def _equipment_counts(
    db: Session, user: User, workspace_id: uuid.UUID, term_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """시험 항목마다 **이 부서의** 장비 수. 카탈로그의 `?workspace=` 와 같은 셈이다."""
    if not term_ids:
        return {}
    owned = visible_equipment_ids(db, user).where(Equipment.owner_workspace_id == workspace_id)
    rows = db.execute(
        select(
            EquipmentTestItem.test_item_term_id,
            func.count(func.distinct(EquipmentTestItem.equipment_id)),
        )
        .where(
            EquipmentTestItem.equipment_id.in_(owned),
            EquipmentTestItem.test_item_term_id.in_(term_ids),
        )
        .group_by(EquipmentTestItem.test_item_term_id)
    ).all()
    return {term_id: int(count) for term_id, count in rows}


def _items_of(db: Session, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[VocabularyTerm]]:
    out: dict[uuid.UUID, list[VocabularyTerm]] = {one: [] for one in test_ids}
    if not test_ids:
        return out
    for test_id, term in db.execute(
        select(ReliabilityTestItem.reliability_test_id, VocabularyTerm)
        .join(VocabularyTerm, VocabularyTerm.id == ReliabilityTestItem.test_item_term_id)
        .where(ReliabilityTestItem.reliability_test_id.in_(test_ids))
        .order_by(VocabularyTerm.value)
    ).all():
        out[test_id].append(term)
    return out


def _outs(db: Session, user: User, rows: list[ReliabilityTest]) -> list[ReliabilityTestOut]:
    """목록 하나를 질의 몇 번으로 — 줄마다 세면 부서 하나에 시험 50건이 질의 150번이 된다."""
    if not rows:
        return []
    workspace_ids = {r.workspace_id for r in rows}
    workspaces = {
        w.id: w for w in db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids)))
    }
    items = _items_of(db, [r.id for r in rows])
    attribute_values = attributes.values_of(
        db, target="reliability_test", object_ids=[r.id for r in rows]
    )
    counts_by_workspace: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for workspace_id in workspaces:
        term_ids = sorted(
            {t.id for r in rows if r.workspace_id == workspace_id for t in items[r.id]}
        )
        counts_by_workspace[workspace_id] = _equipment_counts(db, user, workspace_id, term_ids)
    editable = {wid: _can_edit(db, user, wid) for wid in workspaces}
    out: list[ReliabilityTestOut] = []
    for row in rows:
        workspace = workspaces[row.workspace_id]
        counts = counts_by_workspace[row.workspace_id]
        out.append(
            ReliabilityTestOut(
                id=row.id,
                workspace_slug=workspace.slug,
                workspace_name=workspace.name,
                name=row.name,
                purpose=row.purpose,
                test_items=[
                    ReliabilityTestItemOut(
                        term_id=t.id, value=t.value, equipment_count=counts.get(t.id, 0)
                    )
                    for t in items[row.id]
                ],
                attributes=attribute_values[row.id],
                can_edit=editable[row.workspace_id],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return out


def test_out(db: Session, user: User, row: ReliabilityTest) -> ReliabilityTestOut:
    return _outs(db, user, [row])[0]


def list_for_workspace(db: Session, user: User, slug: str) -> list[ReliabilityTestOut]:
    workspace = workspace_by_slug(db, slug)
    rows = list(
        db.scalars(
            select(ReliabilityTest)
            .where(
                ReliabilityTest.workspace_id == workspace.id,
                ReliabilityTest.deleted_at.is_(None),
            )
            .order_by(ReliabilityTest.name)
        )
    )
    return _outs(db, user, rows)


def get(db: Session, test_id: uuid.UUID) -> ReliabilityTest:
    row = db.get(ReliabilityTest, test_id)
    if row is None or row.deleted_at is not None:
        raise NotFound("TSC-RELIABILITY-0001", "신뢰성 시험을 찾을 수 없습니다.")
    return row


def _check_test_item_terms(db: Session, term_ids: list[uuid.UUID]) -> None:
    """**시험 항목 축의 살아 있는 값만** 받는다. 다른 축의 id 를 받아 두면 화면이
    「인장」 자리에 「3동」 을 그린다."""
    if not term_ids:
        return
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    if axis is None:
        raise AppError("TSC-RELIABILITY-0002", "시험 항목 축이 없습니다.")
    valid = set(
        db.scalars(
            select(VocabularyTerm.id).where(
                VocabularyTerm.vocabulary_id == axis.id,
                VocabularyTerm.id.in_(term_ids),
                VocabularyTerm.status == "active",
            )
        )
    )
    missing = [str(one) for one in term_ids if one not in valid]
    if missing:
        raise AppError(
            "TSC-RELIABILITY-0002",
            "시험 항목이 아니거나 없는 값이 있습니다.",
            details={"term_ids": missing},
        )


def _check_name_free(
    db: Session, workspace_id: uuid.UUID, name: str, *, except_id: uuid.UUID | None
) -> None:
    clash = db.scalar(
        select(ReliabilityTest).where(
            ReliabilityTest.workspace_id == workspace_id,
            ReliabilityTest.deleted_at.is_(None),
            func.lower(ReliabilityTest.name) == name.lower(),
            ReliabilityTest.id != except_id if except_id else true(),
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-RELIABILITY-0003", f"이 부서에 같은 이름의 신뢰성 시험이 있습니다: {name}"
        )


def _set_items(db: Session, test_id: uuid.UUID, term_ids: list[uuid.UUID]) -> None:
    for link in db.scalars(
        select(ReliabilityTestItem).where(ReliabilityTestItem.reliability_test_id == test_id)
    ):
        db.delete(link)
    db.flush()
    for term_id in dict.fromkeys(term_ids):
        db.add(ReliabilityTestItem(reliability_test_id=test_id, test_item_term_id=term_id))


def _attribute_items(raw: Any) -> list[AttributeValueIn]:
    """`model_dump` 를 거쳐 dict 로 온 것을 되돌린다 — 값 검증은 attributes 서비스가 한다."""
    return [
        one if isinstance(one, AttributeValueIn) else AttributeValueIn.model_validate(one)
        for one in (raw or [])
    ]


def create(db: Session, user: User, payload: dict[str, Any]) -> ReliabilityTest:
    workspace = workspace_by_slug(db, payload["workspace_slug"])
    require_manager(db, workspace=workspace, user=user)
    name = str(payload["name"]).strip()
    if not name:
        raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주세요.")
    _check_name_free(db, workspace.id, name, except_id=None)
    term_ids: list[uuid.UUID] = list(payload.get("test_item_term_ids") or [])
    _check_test_item_terms(db, term_ids)

    row = ReliabilityTest(
        workspace_id=workspace.id,
        name=name,
        purpose=str(payload.get("purpose") or "").strip(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _set_items(db, row.id, term_ids)
    attributes.set_values(
        db,
        user,
        target="reliability_test",
        object_id=row.id,
        items=_attribute_items(payload.get("attributes")),
    )
    db.commit()
    db.refresh(row)
    return row


def update(
    db: Session, user: User, test_id: uuid.UUID, changes: dict[str, Any]
) -> ReliabilityTest:
    """`changes` 는 `exclude_unset` 으로 온다 — 안 보낸 칸은 안 건드린다."""
    row = get(db, test_id)
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    require_manager(db, workspace=workspace, user=user)

    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주세요.")
        _check_name_free(db, workspace.id, name, except_id=row.id)
        row.name = name
    if "purpose" in changes:
        row.purpose = str(changes["purpose"] or "").strip()
    if changes.get("test_item_term_ids") is not None:
        term_ids = list(changes["test_item_term_ids"])
        _check_test_item_terms(db, term_ids)
        _set_items(db, row.id, term_ids)
    if changes.get("attributes") is not None:
        attributes.set_values(
            db,
            user,
            target="reliability_test",
            object_id=row.id,
            items=_attribute_items(changes["attributes"]),
        )
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, test_id: uuid.UUID) -> None:
    row = get(db, test_id)
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    require_manager(db, workspace=workspace, user=user)
    row.deleted_at = datetime.now(UTC)
    # **반년 뒤에 「그 시험 어디 갔어」 를 묻는다.** 지운 줄은 화면에서 사라지므로 여기 남는다.
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_DELETED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        target_label=f"{workspace.name} · {row.name}",
        workspace_id=workspace.id,
    )
    db.commit()
