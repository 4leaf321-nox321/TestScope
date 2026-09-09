"""보유 장비 로직 — **우리가 가진 것.**

모델 카탈로그(제조사가 파는 것)는 `catalog.py` 가 맡는다. 나눈 이유는 ADR 0004.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.capabilities.models import Capability
from app.modules.equipment import catalog
from app.modules.equipment.models import (
    EQUIPMENT_STATUSES,
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
)
from app.modules.equipment.schemas import CalibrationOut, EquipmentOut
from app.modules.vocabulary.models import VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict
from app.shared.pagination import Page
from app.shared.permissions import (
    get_equipment,
    require_owner_edit,
    resolve_owner_workspace,
    visible_equipment,
)
from app.shared.text import clean

logger = logging.getLogger(__name__)

_WHAT = "장비"
_CODE = "TAS-EQUIPMENT-0002"


def _term_value(db: Session, term_id: uuid.UUID | None) -> str | None:
    if term_id is None:
        return None
    term = db.get(VocabularyTerm, term_id)
    return term.value if term else None


def _capability_count(db: Session, equipment_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Capability)
            .where(Capability.equipment_id == equipment_id)
        )
        or 0
    )


def _test_items(db: Session, equipment_id: uuid.UUID) -> list[str]:
    """이 장비가 하는 시험 항목 이름들. **목록 한 줄에서 바로 보여야 한다.**

    역량을 열어 봐야 아는 화면은 「우리가 무슨 시험을 할 수 있나」 에 답하지 못한다 —
    그 물음이 이 시스템이 존재하는 이유다.
    """
    rows = db.scalars(
        select(VocabularyTerm.value)
        .join(Capability, Capability.test_item_term_id == VocabularyTerm.id)
        .where(Capability.equipment_id == equipment_id)
        .order_by(VocabularyTerm.value)
        .distinct()
    )
    return list(rows)


def _latest_due(db: Session, equipment_id: uuid.UUID) -> Any:
    return db.scalar(
        select(EquipmentCalibration.next_due_on)
        .where(EquipmentCalibration.equipment_id == equipment_id)
        .order_by(EquipmentCalibration.calibrated_on.desc())
        .limit(1)
    )


def _can_edit(db: Session, user: User, row: Equipment) -> bool:
    """고칠 수 있는가. **판정 로직을 재사용한다** — 화면이 스스로 계산하면
    버튼은 보이는데 누르면 403 인 상태가 생긴다."""
    try:
        require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    except AppError:
        return False
    return True


def equipment_out(db: Session, row: Equipment, viewer: User) -> EquipmentOut:
    workspace = db.get(Workspace, row.owner_workspace_id) if row.owner_workspace_id else None
    contact = db.get(User, row.contact_user_id) if row.contact_user_id else None
    model = db.get(EquipmentModel, row.model_id) if row.model_id else None
    series = db.get(EquipmentSeries, model.series_id) if model else None
    return EquipmentOut(
        id=row.id,
        asset_no=row.asset_no,
        name=row.name,
        model_id=row.model_id,
        model_name=model.name if model else None,
        series_id=model.series_id if model else None,
        series_name=series.name if series else None,
        # **카탈로그에서 끌어온다.** 개체는 이 둘을 갖지 않는다(ADR 0004).
        # 계열이 갖는 값이라 기종을 거쳐 두 단계로 간다(ADR 0006).
        category=_term_value(db, series.category_term_id) if series else None,
        manufacturer=_term_value(db, series.maker_term_id) if series else None,
        serial_no=row.serial_no,
        workspace_slug=workspace.slug if workspace else None,
        workspace_name=workspace.name if workspace else None,
        site=_term_value(db, row.site_term_id),
        location=row.location,
        status=row.status,
        acquired_on=row.acquired_on,
        contact_name=contact.display_name if contact else None,
        note=row.note,
        capability_count=_capability_count(db, row.id),
        test_items=_test_items(db, row.id),
        calibration_due_on=_latest_due(db, row.id),
        created_at=row.created_at,
        can_edit=_can_edit(db, viewer, row),
    )


def list_equipment(
    db: Session,
    user: User,
    *,
    query: str | None,
    status: str | None,
    workspace_slug: str | None,
    model_id: uuid.UUID | None = None,
    limit: int,
    offset: int,
) -> Page[EquipmentOut]:
    stmt = visible_equipment(db, user)
    if query:
        text = f"%{clean(query)}%"
        # 자산번호와 이름 둘 다 본다 — 사람은 현장에서 라벨의 번호를 치고, 회의
        # 에서는 이름을 친다.
        stmt = stmt.where(Equipment.asset_no.ilike(text) | Equipment.name.ilike(text))
    if model_id is not None:
        # **서버가 거른다.** 화면이 전체 목록을 받아 걸러 내면, 상한(200)을 넘는
        # 순간 나머지가 조용히 안 보인다 — 그리고 그때 그 기종은 「보유 없음」 이
        # 되어 카탈로그가 거짓말을 한다.
        stmt = stmt.where(Equipment.model_id == model_id)
    if status:
        stmt = stmt.where(Equipment.status == status)
    if workspace_slug:
        workspace = db.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
        stmt = stmt.where(
            Equipment.owner_workspace_id == (workspace.id if workspace else None)
        )

    # **total 을 함께 준다.** 없으면 화면이 다음 쪽 유무를 알려고 한 건 더 요청하는
    # 편법을 쓰게 되고, 그 편법은 화면마다 달라진다.
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Equipment.asset_no).limit(limit).offset(offset))
    return Page(
        items=[equipment_out(db, row, user) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def create(db: Session, user: User, payload: dict[str, Any]) -> Equipment:
    asset_no = clean(payload["asset_no"])
    if db.scalar(select(Equipment).where(Equipment.asset_no == asset_no)) is not None:
        raise Conflict("TAS-EQUIPMENT-0003", f"이미 등록된 자산번호입니다: {asset_no}")

    status = payload.get("status") or "operational"
    if status not in EQUIPMENT_STATUSES:
        raise AppError("TAS-EQUIPMENT-0004", f"모르는 상태입니다: {status}", status=400)

    owner = resolve_owner_workspace(
        db, user, payload.get("workspace_slug"), what=_WHAT, code=_CODE
    )
    row = Equipment(
        asset_no=asset_no,
        name=clean(payload["name"]),
        owner_workspace_id=owner,
        model_id=payload.get("model_id"),
        serial_no=payload.get("serial_no"),
        site_term_id=payload.get("site_term_id"),
        location=payload.get("location"),
        status=status,
        acquired_on=payload.get("acquired_on"),
        contact_user_id=payload.get("contact_user_id"),
        note=payload.get("note"),
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()

    # **모델을 골랐으면 사양서 역량을 이 장비로 복사한다.** 같은 트랜잭션이어야
    # "장비는 생겼는데 역량만 없는" 상태가 안 생긴다(ADR 0004).
    copied = catalog.copy_capabilities_to(db, row, user)

    db.commit()
    db.refresh(row)
    if copied:
        logger.info("장비 %s: 카탈로그 역량 %d건 복사", row.asset_no, copied)
    return row


#: 부분 수정에서 그대로 옮겨 담는 칸들. 이 목록에 없는 것(부서 이관·상태)은
#: 판단이 따로 붙으므로 아래에서 손으로 다룬다.
_PLAIN_FIELDS = (
    "name",
    "model_id",
    "serial_no",
    "site_term_id",
    "location",
    "acquired_on",
    "contact_user_id",
    "note",
)


def update(
    db: Session, user: User, equipment_id: uuid.UUID, changes: dict[str, Any]
) -> Equipment:
    """**보낸 것만 바꾼다.** changes 는 exclude_unset 으로 만들어진 dict 다."""
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)

    if "workspace_slug" in changes:
        # 이관은 **양쪽 다 관리자**여야 한다. 받는 쪽 권한을 안 보면 남의 부서에
        # 장비를 밀어 넣을 수 있고, 그 부서는 자기가 안 만든 장비를 떠안는다.
        row.owner_workspace_id = resolve_owner_workspace(
            db, user, changes["workspace_slug"], what=_WHAT, code=_CODE
        )

    if "status" in changes and changes["status"] is not None:
        status = changes["status"]
        if status not in EQUIPMENT_STATUSES:
            raise AppError("TAS-EQUIPMENT-0004", f"모르는 상태입니다: {status}", status=400)
        if status != row.status:
            # **폐기만 감사에 남긴다.** 점검·수리는 오가는 상태라 다 남기면 그
            # 안에서 정작 찾을 것을 못 찾는다. 폐기는 목록에서 사라지는 일이다.
            if status == "retired":
                audit.record(
                    db,
                    action=audit.EQUIPMENT_RETIRED,
                    actor=user,
                    target_table="equipment",
                    target_id=row.id,
                    target_label=f"{row.asset_no} {row.name}",
                    workspace_id=row.owner_workspace_id,
                    changes={"status": {"before": row.status, "after": status}},
                )
            row.status = status

    for field in _PLAIN_FIELDS:
        if field in changes:
            setattr(row, field, changes[field])

    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, equipment_id: uuid.UUID) -> None:
    """소프트 삭제. **행은 남는다** — 이 장비로 잰 데이터가 밖에 있고, 몇 년 뒤에도
    그것이 어느 장비였는지는 물어질 수 있다."""
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    audit.record(
        db,
        action=audit.EQUIPMENT_DELETED,
        actor=user,
        target_table="equipment",
        target_id=row.id,
        target_label=f"{row.asset_no} {row.name}",
        workspace_id=row.owner_workspace_id,
    )
    row.deleted_at = datetime.now(UTC)
    db.commit()


# --- 교정 -------------------------------------------------------------------


def calibrations(db: Session, user: User, equipment_id: uuid.UUID) -> list[CalibrationOut]:
    get_equipment(db, user, equipment_id)
    rows = db.scalars(
        select(EquipmentCalibration)
        .where(EquipmentCalibration.equipment_id == equipment_id)
        .order_by(EquipmentCalibration.calibrated_on.desc())
    )
    return [CalibrationOut.model_validate(row) for row in rows]


def add_calibration(
    db: Session, user: User, equipment_id: uuid.UUID, payload: dict[str, Any]
) -> CalibrationOut:
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    record = EquipmentCalibration(equipment_id=row.id, **payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return CalibrationOut.model_validate(record)
