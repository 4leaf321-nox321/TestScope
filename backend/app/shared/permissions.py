"""권한 판정 — 부서 스코프. **판정 지점이 하나여야 한다.**

가시성과 수정 권한을 각 쿼리에 흩뿌리면 "목록에는 보이는데 상세는 403" 같은
어긋남이 생기고, 그때 어느 쪽이 맞는지 알 방법이 없다.

시스템 역할과 부서 역할은 **다른 축**이다.
  - is_system_admin : 전사. 계정·부서 자체를 만들고 지운다
  - 부서 manager    : 그 부서 안에서만. 멤버와 장비를 관리한다
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, Select, or_, select, true
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.modules.accounts.models import User
from app.modules.equipment.models import Equipment
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.shared.errors import Forbidden, NotFound


def division_map(db: Session) -> dict[uuid.UUID, uuid.UUID | None]:
    """부서마다 **효력 있는 사업부**(`division` 축의 값 id). 없으면 None.

    부서에 안 붙어 있으면 조직도를 타고 **올라가** 처음 만나는 값이 그 부서의 사업부다.
    사업부에 한 번 붙이면 그 아래 수십 개 팀에 다시 붙일 일이 없고, 팀이 다른 사업부로
    옮겨 가면 부모만 바뀌어도 따라간다 — 값을 팀마다 적어 두면 개편 때마다 전부 고쳐야
    하고, 한 줄 빠뜨리면 그 팀의 시험이 엉뚱한 사업부로 올라간다.

    **한 번에 다 계산한다.** 부서마다 조상을 거슬러 물으면 목록 한 장에 질의가 부서 수만큼
    난다(트리가 깊을수록 더).
    """
    rows = list(db.scalars(select(Workspace)))
    by_id = {row.id: row for row in rows}
    resolved: dict[uuid.UUID, uuid.UUID | None] = {}

    def walk(node: Workspace, seen: set[uuid.UUID]) -> uuid.UUID | None:
        if node.id in resolved:
            return resolved[node.id]
        if node.division_term_id is not None:
            resolved[node.id] = node.division_term_id
            return node.division_term_id
        parent = by_id.get(node.parent_id) if node.parent_id else None
        # 고리가 있어도 멈춘다 — 조직도가 꼬였다고 목록이 통째로 안 뜨면 고칠 수도 없다.
        found = None if parent is None or parent.id in seen else walk(parent, seen | {node.id})
        resolved[node.id] = found
        return found

    for row in rows:
        walk(row, set())
    return resolved


def my_division_term_ids(db: Session, user: User) -> set[uuid.UUID]:
    """이 사람이 **데이터를 올릴 수 있는** 사업부들.

    내 소속 중 **관리자 역할**인 부서의 사업부다(멤버는 읽기만 — 저장소의 기존 규칙을
    그대로 두고 축만 부서에서 사업부로 옮긴 것이다). HE팀 관리자면 그 위 MX 사업부에
    올릴 수 있다.

    시스템 관리자는 여기를 안 지난다 — 모든 사업부에 올릴 수 있고, 부를 쪽이 먼저 본다.
    """
    mine = db.scalars(
        select(WorkspaceMember.workspace_id).where(
            WorkspaceMember.user_id == user.id, WorkspaceMember.role == "manager"
        )
    )
    divisions = division_map(db)
    return {found for wid in mine if (found := divisions.get(wid)) is not None}


def workspace_by_slug(db: Session, slug: str) -> Workspace:
    workspace = db.scalar(select(Workspace).where(Workspace.slug == slug))
    if workspace is None:
        raise NotFound("TSC-WORKSPACES-0001", f"부서를 찾을 수 없음: {slug}")
    return workspace


def membership_of(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    return db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )


def require_member(db: Session, *, workspace: Workspace, user: User) -> None:
    """그 부서를 볼 수 있는가. 시스템 관리자는 모든 부서를 본다."""
    if user.is_system_admin:
        return
    if membership_of(db, workspace_id=workspace.id, user_id=user.id) is None:
        raise Forbidden("TSC-WORKSPACES-0002", "이 부서에 대한 접근 권한 없음.")


def require_manager(db: Session, *, workspace: Workspace, user: User) -> None:
    """그 부서의 멤버·장비를 바꿀 수 있는가."""
    if user.is_system_admin:
        return
    membership = membership_of(db, workspace_id=workspace.id, user_id=user.id)
    if membership is None or membership.role != "manager":
        raise Forbidden("TSC-WORKSPACES-0003", "부서 관리자 전용 작업.")


def my_workspace_ids(db: Session, user: User) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
        )
    )


def is_any_manager(db: Session, user: User) -> bool:
    """어느 부서든 관리자인가. 화면이 만들기 버튼을 보일지 판단하는 근거다."""
    if user.is_system_admin:
        return True
    return (
        db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.user_id == user.id, WorkspaceMember.role == "manager"
            )
        )
        is not None
    )


# --- 부서 소유 자산 ---------------------------------------------------------
#
# 장비와 시험법이 **같은 소유 모델**을 쓴다: owner_workspace_id 가 NULL 이면 전역,
# 아니면 그 부서 것. 판정을 각 모듈이 따로 적으면 "시험법은 되는데 장비는 안 되는"
# 식으로 어긋나고, 그 어긋남이 부서 관리자를 막다른 길로 보낸다.


def visible_owner_clause(
    user: User, column: InstrumentedAttribute[uuid.UUID | None]
) -> ColumnElement[bool]:
    """전역 + 내 부서 필터. 목록·조회·검색이 **같은 것**을 봐야 한다."""
    if user.is_system_admin:
        return true()
    mine = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    return or_(column.is_(None), column.in_(mine))


def _require_role(db: Session, *, workspace: Workspace, user: User, role: str) -> None:
    """`member` 면 그 부서 사람이면 되고, `manager` 면 부서 관리자여야 한다.

    **기본은 manager 다.** 부르는 쪽이 `member` 라고 적어야 열린다 — 자격이 넓어지는
    일은 호출 자리에 보여야 하고, 기본값이 넓으면 새로 생긴 경로가 조용히 열린다.
    """
    if role == "member":
        require_member(db, workspace=workspace, user=user)
    else:
        require_manager(db, workspace=workspace, user=user)


def resolve_owner_workspace(
    db: Session,
    user: User,
    slug: str | None,
    *,
    what: str,
    code: str,
    role: str = "manager",
) -> uuid.UUID | None:
    """만들 때 누구 것으로 할지. None 이면 전역 — 시스템 관리자만."""
    if slug is None:
        if not user.is_system_admin:
            raise Forbidden(
                code, f"전역 {what}은(는) 시스템 관리자만 등록 가능. 부서 선택 필요."
            )
        return None
    workspace = workspace_by_slug(db, slug)
    _require_role(db, workspace=workspace, user=user, role=role)
    return workspace.id


def require_owner_edit(
    db: Session,
    user: User,
    owner_workspace_id: uuid.UUID | None,
    *,
    what: str,
    code: str,
    role: str = "manager",
) -> None:
    """고칠 수 있는가.

    전역은 **여러 부서가 함께 쓴다.** 한 부서가 고치면 다른 부서의 데이터가 다르게
    읽힌다 — 그래서 전역은 시스템 관리자만 손댄다.

    **보유 장비는 `role="member"` 로 부른다**(2026-09-23). 장비를 쓰는 사람이 그 장비를
    등록하고 시험 항목을 적는다 — 부서 관리자를 거치게 하면 등록이 밀리고, 밀린 장비는
    검색에 안 걸린다. 그리고 등록만 열고 수정을 막는 것이 더 나쁘다: 제가 넣은 오타를
    못 고치고, 무엇보다 **시험 항목을 못 달아 그 장비가 영영 검색에 안 걸린다.**
    부서의 운영(멤버·신뢰성 시험·부서 규격)은 여전히 관리자다.
    """
    if user.is_system_admin:
        return
    if owner_workspace_id is None:
        raise Forbidden(
            code,
            f"전역 {what}은(는) 시스템 관리자만 수정 가능.",
        )
    workspace = db.get(Workspace, owner_workspace_id)
    if workspace is None:
        raise NotFound(code, f"{what}의 소속 부서를 찾을 수 없음.")
    _require_role(db, workspace=workspace, user=user, role=role)


# --- 장비의 가시 범위 -------------------------------------------------------


def visible_equipment(db: Session, user: User) -> Select[tuple[Equipment]]:
    """전역 장비 + 열린 부서의 장비 + 내 부서 장비.

    **가리는 쪽이 예외다.** 이 시스템이 답하려는 물음("우리 조직에 그 시험이 가능한
    장비가 있나")은 부서를 가로지른다 — 자기 부서 것만 보이면 그 물음에 아무도
    답할 수 없고, 그러면 사람은 예전처럼 전화를 돌린다.

    쓰기는 이것과 무관하다. 보이는 것과 고칠 수 있는 것은 다른 축이고, 고치는 쪽은
    여전히 소유 부서의 관리자다(require_owner_edit).
    """
    query = select(Equipment).where(Equipment.deleted_at.is_(None))
    if user.is_system_admin:
        return query
    mine = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    opened = select(Workspace.id).where(Workspace.restricted.is_(False))
    return query.where(
        or_(
            Equipment.owner_workspace_id.is_(None),
            Equipment.owner_workspace_id.in_(opened),
            Equipment.owner_workspace_id.in_(mine),
        )
    )


def visible_equipment_ids(db: Session, user: User) -> Select[tuple[uuid.UUID]]:
    """하위 쿼리(시험 항목·검색)에 끼워 넣을 서브쿼리. visible_equipment 와 **같은 조건**이다.

    같은 규칙을 두 번 적으면 언젠가 한쪽만 고쳐지고, 그때 검색 결과와 목록이 서로
    다른 장비를 보여 준다.
    """
    return visible_equipment(db, user).with_only_columns(Equipment.id)


def get_equipment(db: Session, user: User, equipment_id: uuid.UUID) -> Equipment:
    found = db.scalar(visible_equipment(db, user).where(Equipment.id == equipment_id))
    if found is None:
        raise NotFound("TSC-EQUIPMENT-0001", "장비를 찾을 수 없음.")
    return found
