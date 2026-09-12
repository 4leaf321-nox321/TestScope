"""알림이 **언제 누구에게** 가는가 — 규칙은 여기 한 곳에 있다.

표와 화면은 있었는데 알림을 만드는 곳이 없었다(2026-09-12 실측: `notify()` 를 부르는
코드 0). 메일이 없는 환경이라 이것이 유일한 전달 경로인데, 아무 일에도 안 울리는 종은
곧 아무도 안 본다.

## 규칙

- **가입 신청** → 시스템 관리자 전원. 승인은 관리자만 한다 — 홈의 「남은 일」 도 세지만
  그건 들어가야 보인다.
- **가입 승인** → 신청한 사람. 로그인해서 처음 보는 것이 「승인됐다」 여야 한다.
- **장비 상태 변경** → 소유 부서의 관리자(바꾼 사람 제외). 폐기·고장은 그 부서가 알아야
  할 일이고, 관리자가 장비를 책임진다.
- **교정 만료 임박·초과** → 소유 부서의 관리자. 외부 교정을 잡는 사람. 60일 전과 지난 뒤
  두 번.

가입 **거절**은 안 보낸다 — 거절된 계정은 로그인을 못 하니 읽을 수 없고, 읽을 수 없는
알림은 「보냈다」 는 기록만 남긴다. 사유는 계정의 `decision_note` 에 있다.

## 교정은 훑기가 만든다

사람이 무언가를 해서 생기는 알림이 아니라 **날이 되면** 생기는 알림이다. 스케줄러가 없으니
알림을 읽는 요청이 올 때 그 사람 몫만 훑는다(`sweep_calibration`). 같은 장비의 같은
만료일에는 한 번만 — `dedupe_key` 가 막는다. 두 번 가면 사람은 알림을 안 읽게 된다.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment, EquipmentCalibration
from app.modules.notifications import services
from app.modules.workspaces.models import Workspace, WorkspaceMember

#: 교정 만료를 「곧」 으로 볼 기간. 서버 화면의 「곧 만료」 와 같은 60일이다.
CALIBRATION_HORIZON_DAYS = 60

#: 상태의 한글 이름. 화면(`equipment/status.ts`)과 같아야 한다.
STATUS_LABEL = {
    "incoming": "입고",
    "operational": "가동",
    "idle": "유휴",
    "maintenance": "점검·교정",
    "repair": "고장",
    "retired": "폐기",
}


def _admins(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).where(
                User.is_system_admin.is_(True),
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
    )


def _managers(db: Session, workspace_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(WorkspaceMember.user_id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "manager",
            )
        )
    )


def signup_requested(db: Session, user: User) -> None:
    """가입 신청 → 시스템 관리자 전원."""
    workspace = (
        db.get(Workspace, user.requested_workspace_id) if user.requested_workspace_id else None
    )
    where = f" · 신청 부서 {workspace.name}" if workspace else ""
    for admin in _admins(db):
        services.notify(
            db,
            user_id=admin.id,
            kind=services.ACCOUNT_PENDING,
            title=f"가입 신청: {user.display_name}",
            body=f"{user.email}{where}",
            link="/admin/accounts?status=pending",
            dedupe_key=f"{services.ACCOUNT_PENDING}:{user.id}",
        )


def account_approved(db: Session, user: User, workspace: Workspace) -> None:
    """가입 승인 → 신청한 사람. 로그인해서 처음 보는 것이 이것이어야 한다."""
    services.notify(
        db,
        user_id=user.id,
        kind=services.ACCOUNT_APPROVED,
        title="가입이 승인되었습니다",
        body=f"소속 부서: {workspace.name}",
        link="/",
        dedupe_key=f"{services.ACCOUNT_APPROVED}:{user.id}",
    )


def equipment_status_changed(
    db: Session, equipment: Equipment, *, before: str, after: str, actor: User
) -> None:
    """장비 상태 변경 → 소유 부서의 관리자(바꾼 사람 제외)."""
    for user_id in _managers(db, equipment.owner_workspace_id):
        if user_id == actor.id:
            continue
        services.notify(
            db,
            user_id=user_id,
            kind=services.EQUIPMENT_STATUS_CHANGED,
            title=f"{equipment.asset_no} {equipment.name}: "
            f"{STATUS_LABEL.get(before, before)} → {STATUS_LABEL.get(after, after)}",
            body=f"{actor.display_name or actor.email} 이(가) 바꿈",
            link=f"/equipment/{equipment.id}",
        )


def sweep_calibration(db: Session, user: User, *, today: date | None = None) -> int:
    """이 사람이 관리하는 부서의 장비 중 교정이 곧 만료되거나 지난 것을 알린다. 새로 만든 수.

    장비마다 **가장 최근 교정 하나**만 본다. 이력을 다 보면 옛 교정의 지난 예정일이
    매번 경고로 뜬다 — 이미 다시 받은 장비인데도. 성적서에 적힌 차기일만 본다:
    주기로 계산한 날은 짐작이라, 짐작으로 알림을 울리면 곧 알림을 안 믿는다.
    """
    today = today or date.today()
    workspaces = list(
        db.scalars(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user.id, WorkspaceMember.role == "manager"
            )
        )
    )
    if not workspaces:
        return 0
    latest = (
        select(
            EquipmentCalibration.equipment_id,
            func.max(EquipmentCalibration.calibrated_on).label("calibrated_on"),
        )
        .group_by(EquipmentCalibration.equipment_id)
        .subquery()
    )
    rows = db.execute(
        select(Equipment, EquipmentCalibration.next_due_on)
        .join(latest, latest.c.equipment_id == Equipment.id)
        .join(
            EquipmentCalibration,
            (EquipmentCalibration.equipment_id == Equipment.id)
            & (EquipmentCalibration.calibrated_on == latest.c.calibrated_on),
        )
        .where(
            Equipment.owner_workspace_id.in_(workspaces),
            Equipment.deleted_at.is_(None),
            Equipment.status != "retired",
            EquipmentCalibration.next_due_on.is_not(None),
        )
    ).all()
    made = 0
    for equipment, due in rows:
        days_left = (due - today).days
        if days_left > CALIBRATION_HORIZON_DAYS:
            continue
        overdue = days_left < 0
        stage = "overdue" if overdue else "due"
        title = (
            f"{equipment.asset_no} {equipment.name}: 교정 기한 {-days_left}일 지남"
            if overdue
            else f"{equipment.asset_no} {equipment.name}: 교정 {days_left}일 남음"
        )
        row = services.notify(
            db,
            user_id=user.id,
            kind=services.CALIBRATION_DUE,
            title=title,
            body=f"차기 교정일 {due.isoformat()}",
            link=f"/equipment/{equipment.id}",
            dedupe_key=f"{services.CALIBRATION_DUE}:{stage}:{equipment.id}:{due.isoformat()}",
        )
        if row is not None:
            made += 1
    return made
