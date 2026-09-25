"""부서 로직 — 생성·보관, 멤버와 역할.

**부서를 함부로 지우지 않는다.** is_active=false 로 보관하는 것이 기본이다. 부서에는
장비가 매달리고, 장비는 조직보다 오래 산다 — 무엇이 그 부서를 참조하는지 답할 수
있을 때만 삭제를 허용한다(references).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.documents.models import SpecDocument
from app.modules.equipment.models import Equipment
from app.modules.methods.models import TestMethod
from app.modules.reliability.models import ReliabilityTest
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.modules.workspaces.schemas import (
    MemberOut,
    WorkspaceClashOut,
    WorkspaceMoveOut,
    WorkspaceOption,
    WorkspaceOut,
    WorkspaceReassignOut,
    WorkspaceReferenceOut,
)
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.permissions import membership_of, workspace_by_slug

ROLES = ("member", "manager")


def _member_count(db: Session, workspace_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
        or 0
    )


def _equipment_count(db: Session, workspace_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Equipment)
            .where(
                Equipment.owner_workspace_id == workspace_id,
                Equipment.deleted_at.is_(None),
            )
        )
        or 0
    )


# --- 트리 --------------------------------------------------------------------


def ordered_tree(db: Session) -> list[tuple[Workspace, int, str]]:
    """(부서, 깊이, 경로) 를 **트리 순서**로. 화면은 이 순서 그대로 그린다.

    순서를 서버가 정하는 이유: 화면이 평면 목록을 받아 스스로 트리를 세우면, 부서
    선택기·관리 화면·가입 화면이 각자 다른 정렬을 갖게 된다. 조직도의 순서는 한
    곳에서만 정해져야 한다.

    부모가 없는(끊어진) 행도 뿌리로 취급해 반드시 내보낸다. 데이터가 이상해도
    **화면에서 사라지는 것이 가장 나쁘다** — 사라지면 고칠 수도 없다.
    """
    rows = list(db.scalars(select(Workspace)))
    by_parent: dict[uuid.UUID | None, list[Workspace]] = {}
    known = {row.id for row in rows}
    for row in rows:
        parent = row.parent_id if row.parent_id in known else None
        by_parent.setdefault(parent, []).append(row)
    for siblings in by_parent.values():
        siblings.sort(key=lambda item: (item.sort_order, item.name))

    out: list[tuple[Workspace, int, str]] = []

    def walk(parent: uuid.UUID | None, depth: int, prefix: str) -> None:
        for node in by_parent.get(parent, []):
            path = f"{prefix} / {node.name}" if prefix else node.name
            out.append((node, depth, path))
            walk(node.id, depth + 1, path)

    walk(None, 0, "")

    # 순환이 생겨 walk 가 못 닿은 행이 있으면 뒤에 붙인다. 조용히 빠뜨리지 않는다.
    reached = {node.id for node, _, _ in out}
    for row in rows:
        if row.id not in reached:
            out.append((row, 0, f"{row.name} (연결 끊김)"))
    return out


def _descendant_ids(db: Session, workspace_id: uuid.UUID) -> set[uuid.UUID]:
    """자신 + 모든 하위. 부모를 바꿀 때 순환을 막는 데 쓴다."""
    rows = list(db.scalars(select(Workspace)))
    by_parent: dict[uuid.UUID | None, list[Workspace]] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)

    found = {workspace_id}
    stack = [workspace_id]
    while stack:
        current = stack.pop()
        for child in by_parent.get(current, []):
            if child.id not in found:
                found.add(child.id)
                stack.append(child.id)
    return found


def workspace_out(
    db: Session,
    workspace: Workspace,
    viewer: User,
    *,
    depth: int | None = None,
    path: str | None = None,
    parent_slug: str | None = None,
) -> WorkspaceOut:
    """트리 위치는 **안 주면 스스로 찾는다.**

    목록은 이미 한 번 순회했으니 그 값을 넘겨 준다. 단건 응답(만들기·옮기기)은
    넘길 값이 없는데, 그때 깊이 0·경로=이름으로 두면 방금 자식으로 만든 부서가
    화면에서 뿌리로 보인다.
    """
    if depth is None or path is None:
        for node, node_depth, node_path in ordered_tree(db):
            if node.id == workspace.id:
                depth, path = node_depth, node_path
                if node.parent_id:
                    parent = db.get(Workspace, node.parent_id)
                    parent_slug = parent.slug if parent else None
                break

    membership = membership_of(db, workspace_id=workspace.id, user_id=viewer.id)
    return WorkspaceOut(
        id=workspace.id,
        slug=workspace.slug,
        name=workspace.name,
        parent_slug=parent_slug,
        depth=depth or 0,
        path=path or workspace.name,
        sort_order=workspace.sort_order,
        restricted=workspace.restricted,
        reliability_listed=workspace.reliability_listed,
        is_active=workspace.is_active,
        created_at=workspace.created_at,
        member_count=_member_count(db, workspace.id),
        equipment_count=_equipment_count(db, workspace.id),
        my_role=membership.role if membership else None,
    )


def options(db: Session) -> list[WorkspaceOption]:
    """가입 신청 화면용. 인증 없이 나가므로 이름과 주소만 담는다."""
    return [
        WorkspaceOption(slug=node.slug, name=node.name, path=path, depth=depth)
        for node, depth, path in ordered_tree(db)
        if node.is_active
    ]


def reliability_listed(db: Session) -> list[WorkspaceOption]:
    """사이드바 「신뢰성 시험」 아래에 설 부서들 — **소속과 무관하게 누구나 본다.**

    이 시스템의 물음은 부서를 가로지른다(「저 부서는 무슨 시험을 하나」). 내 소속만
    주면 남의 부서 메뉴가 안 보이고, 그때 사람은 그 부서가 시험을 안 하는 줄 안다.
    보관한 부서는 뺀다 — 메뉴에 남으면 눌러 보고 나서야 없어진 것을 안다."""
    return [
        WorkspaceOption(slug=node.slug, name=node.name, path=path, depth=depth)
        for node, depth, path in ordered_tree(db)
        if node.is_active and node.reliability_listed
    ]


def list_for(db: Session, user: User, *, all_workspaces: bool) -> list[WorkspaceOut]:
    """내 소속만, 또는 전체(시스템 관리자)."""
    mine = set(
        db.scalars(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
        )
    )
    out: list[WorkspaceOut] = []
    for node, depth, path in ordered_tree(db):
        if not all_workspaces and not user.is_system_admin and node.id not in mine:
            continue
        parent = db.get(Workspace, node.parent_id) if node.parent_id else None
        out.append(
            workspace_out(
                db,
                node,
                user,
                depth=depth,
                path=path,
                parent_slug=parent.slug if parent else None,
            )
        )
    return out


def create(
    db: Session, *, slug: str, name: str, creator: User, parent_slug: str | None
) -> Workspace:
    if db.scalar(select(Workspace).where(Workspace.slug == slug)) is not None:
        raise Conflict("TSC-WORKSPACES-0004", f"이미 있는 부서 주소입니다: {slug}")

    parent = workspace_by_slug(db, parent_slug) if parent_slug else None
    # 형제 끝에 붙인다. 순서는 사람이 나중에 바꾼다.
    last = db.scalar(
        select(func.max(Workspace.sort_order)).where(
            Workspace.parent_id == (parent.id if parent else None)
        )
    )
    workspace = Workspace(
        slug=slug,
        name=name,
        parent_id=parent.id if parent else None,
        sort_order=(last or 0) + 1,
    )
    db.add(workspace)
    db.flush()

    # **만든 사람이 그 부서의 관리자로 들어간다.** 안 그러면 방금 만든 부서에
    # 아무도 손댈 수 없고, 첫 멤버를 넣는 것조차 막힌다.
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=creator.id, role="manager"))
    db.commit()
    db.refresh(workspace)
    return workspace


def update(
    db: Session,
    *,
    slug: str,
    name: str | None,
    is_active: bool | None,
    restricted: bool | None,
    reliability_listed: bool | None = None,
) -> Workspace:
    """**안 보낸 것과 비운 것을 구별한다.** None 은 "안 바꿈" 이다 — 구별하지 않으면
    이름만 고칠 때마다 공개 설정이 함께 초기화된다."""
    workspace = workspace_by_slug(db, slug)
    if name is not None:
        workspace.name = name.strip()
    if is_active is not None:
        workspace.is_active = is_active
    if restricted is not None:
        workspace.restricted = restricted
    if reliability_listed is not None:
        workspace.reliability_listed = reliability_listed
    db.commit()
    db.refresh(workspace)
    return workspace


def move(db: Session, *, slug: str, parent_slug: str | None) -> Workspace:
    """상위 부서 바꾸기 — 조직 개편.

    **자료는 하나도 안 움직인다.** 장비는 부서 id 를 가리키고, 트리를 옮겨도 그 id 는
    그대로다. 조직 식별자를 데이터에 직접 박았다면 개편에 대응할 수단이 없다.
    """
    workspace = workspace_by_slug(db, slug)
    if parent_slug is None:
        workspace.parent_id = None
    else:
        parent = workspace_by_slug(db, parent_slug)
        # **자기 하위로는 못 간다.** 막지 않으면 트리에서 통째로 사라지고, 화면에
        # 안 나오니 되돌릴 수도 없다.
        if parent.id in _descendant_ids(db, workspace.id):
            raise AppError(
                "TSC-WORKSPACES-0005",
                "자기 자신이나 하위 부서 아래로는 옮길 수 없습니다.",
                status=400,
            )
        workspace.parent_id = parent.id
    db.commit()
    db.refresh(workspace)
    return workspace


def reorder(db: Session, *, slug: str, direction: str) -> Workspace:
    """형제 사이 순서. 조직도 순서는 이름순도 생성순도 아니다 — 사람이 정한다."""
    workspace = workspace_by_slug(db, slug)
    siblings = sorted(
        db.scalars(select(Workspace).where(Workspace.parent_id == workspace.parent_id)),
        key=lambda item: (item.sort_order, item.name),
    )
    index = next(i for i, item in enumerate(siblings) if item.id == workspace.id)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(siblings):
        siblings[index], siblings[target] = siblings[target], siblings[index]
        # **자리를 통째로 다시 매긴다.** 두 값만 맞바꾸면 옛 데이터에 같은 값이
        # 여럿일 때 순서가 안 바뀐 것처럼 보인다.
        for position, item in enumerate(siblings):
            item.sort_order = position
        db.commit()
    db.refresh(workspace)
    return workspace


@dataclass(frozen=True)
class Reference:
    table: str
    label: str
    count: int
    blocks_delete: bool


def references(db: Session, *, slug: str) -> list[WorkspaceReferenceOut]:
    """무엇이 이 부서를 가리키는가. **삭제 확인 화면이 먼저 부른다.**

    누르기 전에 아는 것이 이 저장소의 무늬다 — 지우고 나서 "장비 12대가 사라졌다"
    를 알게 되면 되돌릴 방법이 없다.
    """
    return [
        WorkspaceReferenceOut(
            table=one.table, label=one.label, count=one.count, blocks_delete=one.blocks_delete
        )
        for one in _counts(db, workspace_by_slug(db, slug))
        if one.count
    ]


def _restricted(
    db: Session, table: str, label: str, model: Any, mine: Any, gone: Any
) -> list[Reference]:
    """RESTRICT 로 막는 표 하나를 **산 것과 지운 것으로 갈라** 센다.

    **지운 줄도 표에는 남아 있고, DB 는 그것까지 보고 막는다.** 산 것만 세면 「가리키는
    것이 없다」 고 답해 놓고 삭제에서 500 이 난다 — 실제로 그랬다(2026-09-25 실측: 시험
    하나를 지운 부서를 지우려 하면 참조 목록은 「멤버 1건」 만 보여 주고 ForeignKeyViolation
    이 났다). 그래서 **세는 자리가 DB 와 같은 눈으로 봐야 한다.**

    갈라 세는 이유는 사람이 읽을 수 있어야 해서다. 「신뢰성 시험 1건」 이라고만 하면 방금
    지운 사람은 「나는 지웠는데?」 가 되고, 어떻게 치워야 하는지 모른다 — 지운 줄은
    이관으로만 따라간다.
    """
    live = db.scalar(select(func.count()).select_from(model).where(mine, gone.is_(None))) or 0
    dropped = (
        db.scalar(select(func.count()).select_from(model).where(mine, gone.is_not(None))) or 0
    )
    return [
        Reference(table, label, live, True),
        Reference(f"{table}_deleted", f"{label}(지운 것)", dropped, True),
    ]


def _counts(db: Session, workspace: Workspace) -> list[Reference]:
    """이 부서를 가리키는 것을 표마다 센다. **세는 자리는 한 곳이다** — 삭제가 막는
    것과 이관이 옮기는 것이 같은 목록이어야, 「막혔는데 옮길 것이 없다」 가 안 생긴다.
    """
    counts = [
        *_restricted(
            db,
            "equipment",
            "장비",
            Equipment,
            Equipment.owner_workspace_id == workspace.id,
            Equipment.deleted_at,
        ),
        *_restricted(
            db,
            "reliability_tests",
            "신뢰성 시험",
            ReliabilityTest,
            ReliabilityTest.workspace_id == workspace.id,
            ReliabilityTest.deleted_at,
        ),
        *_restricted(
            db,
            "spec_documents",
            "사내 규격서",
            SpecDocument,
            SpecDocument.workspace_id == workspace.id,
            SpecDocument.deleted_at,
        ),
        Reference(
            "test_methods",
            "사내 시험법",
            db.scalar(
                select(func.count())
                .select_from(TestMethod)
                .where(TestMethod.owner_workspace_id == workspace.id)
            )
            or 0,
            False,
        ),
        Reference(
            "workspace_members",
            "멤버",
            _member_count(db, workspace.id),
            False,
        ),
        Reference(
            "workspaces",
            "하위 부서",
            db.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.parent_id == workspace.id)
            )
            or 0,
            True,
        ),
    ]
    return counts


def _descendants(db: Session, workspace: Workspace) -> set[uuid.UUID]:
    """이 부서 아래 전부. **이관 대상이 제 자식이면** 먼저 올려야 하기 때문에 본다."""
    found: set[uuid.UUID] = set()
    edge = [workspace.id]
    while edge:
        rows = list(db.scalars(select(Workspace).where(Workspace.parent_id.in_(edge))))
        edge = [row.id for row in rows if row.id not in found]
        found.update(edge)
    return found


def _clashes(db: Session, source: Workspace, target: Workspace) -> list[WorkspaceClashOut]:
    """옮기면 **같은 이름이 둘이 되는 것**을 먼저 찾는다.

    세 표가 「부서 안에서 유일」 을 건다: 장비의 부서 자산번호 · 신뢰성 시험의 이름 ·
    사내 규격서의 문서 번호. 그냥 옮기면 DB 가 막아 500 이 나고, 그때 사람이 보는 것은
    원인이 안 적힌 오류다. **누르기 전에 무엇이 겹치는지 말한다** — 고칠 수 있는 것은
    사람이지 우리가 아니다(둘 중 무엇을 남길지는 우리가 정할 일이 아니다).

    비교는 각 표가 실제로 거는 규칙을 따른다 — 규격서만 대소문자를 무시한다(등록이
    그렇게 거절한다).
    """

    def _names(column: Any, *where: Any) -> list[str]:
        """**`None` 만 뺀다.**

        빈 글자(`''`)는 빼면 안 된다 — 포스트그레스의 유일 제약은 NULL 은 넘어가지만
        `''` 는 값으로 보기 때문에, 양쪽에 하나씩 있으면 옮기는 순간 부딪힌다. 지금은
        문 앞에서 None 으로 바꾸지만(`_none_if_blank`) 그 전에 들어온 줄이 남아 있다.
        """
        return [one for one in db.scalars(select(column).where(*where)) if one is not None]

    def _both(taken: list[str], coming: list[str], *, fold: bool = False) -> list[str]:
        keys = {one.casefold() for one in taken} if fold else set(taken)
        hit = {one for one in coming if (one.casefold() if fold else one) in keys}
        # 빈 글자를 그대로 보이면 화면에 아무것도 안 뜬다 — 무엇이 겹쳤는지 말해 준다.
        return sorted(one or "(빈 값)" for one in hit)

    alive = ReliabilityTest.deleted_at.is_(None)
    live = SpecDocument.deleted_at.is_(None)
    found = [
        WorkspaceClashOut(
            table="equipment",
            label="부서 자산번호",
            values=_both(
                _names(Equipment.dept_asset_no, Equipment.owner_workspace_id == target.id),
                _names(Equipment.dept_asset_no, Equipment.owner_workspace_id == source.id),
            ),
        ),
        WorkspaceClashOut(
            table="reliability_tests",
            label="신뢰성 시험 이름",
            values=_both(
                _names(ReliabilityTest.name, ReliabilityTest.workspace_id == target.id, alive),
                _names(ReliabilityTest.name, ReliabilityTest.workspace_id == source.id, alive),
            ),
        ),
        WorkspaceClashOut(
            table="spec_documents",
            label="사내 규격서 번호",
            values=_both(
                _names(SpecDocument.code, SpecDocument.workspace_id == target.id, live),
                _names(SpecDocument.code, SpecDocument.workspace_id == source.id, live),
                fold=True,
            ),
        ),
    ]
    return [one for one in found if one.values]


def reassign_preview(db: Session, *, slug: str, to: str) -> WorkspaceReassignOut:
    """옮기면 무엇이 어디로 가고, 무엇이 겹치나. **누르기 전에 답한다.**

    삭제 확인 화면이 대상 부서를 고르는 순간 부른다 — 「장비 12대가 옮겨집니다」 를
    보고 누르는 것과, 누르고 나서 아는 것은 다른 일이다.
    """
    source = workspace_by_slug(db, slug)
    target = workspace_by_slug(db, to)
    _check_target(source, target)

    # **옮기는 쪽에서 빠지는 둘은 따로 센다.** 대상 자신은 제 밑으로 안 들어가고,
    # 양쪽에 다 있는 사람은 합쳐지므로 「옮겨진다」 가 아니다 — 미리보기가 그냥 참조 수를
    # 보이면 「하위 부서 3건」 이라 해 놓고 둘만 옮겨 가고, 그때 감사 기록과도 어긋난다.
    planned = {
        "workspaces": len(_children_to_move(db, source, target)),
        "workspace_members": len(_members_to_move(db, source, target)[0]),
    }
    lifted = _lifts_target(db, source, target)
    parent = db.get(Workspace, source.parent_id) if source.parent_id else None
    return WorkspaceReassignOut(
        target_slug=target.slug,
        target_name=target.name,
        moves=[
            WorkspaceMoveOut(
                table=one.table, label=one.label, count=planned.get(one.table, one.count)
            )
            for one in _counts(db, source)
            if planned.get(one.table, one.count)
        ],
        clashes=_clashes(db, source, target),
        # **조직도가 바뀌는 것도 말한다.** 본부를 없애고 그 아래 팀으로 합치면 그 팀이
        # 한 단 올라가고 형제들이 그 밑으로 들어간다 — 두 단짜리 개편을 모르고 누르면 안 된다.
        lifts_target=lifted,
        target_new_parent_name=(parent.name if parent else None) if lifted else None,
    )


def _lifts_target(db: Session, source: Workspace, target: Workspace) -> bool:
    """대상이 지울 부서의 아래에 있나 — 그러면 이관할 때 한 단 올라간다."""
    return target.id in _descendants(db, source)


def _children_to_move(db: Session, source: Workspace, target: Workspace) -> list[Workspace]:
    """대상 아래로 들어갈 하위 부서. **대상 자신은 뺀다** — 제 밑으로 못 들어간다."""
    return list(
        db.scalars(
            select(Workspace).where(
                Workspace.parent_id == source.id, Workspace.id != target.id
            )
        )
    )


def _members_to_move(
    db: Session, source: Workspace, target: Workspace
) -> tuple[list[WorkspaceMember], list[tuple[WorkspaceMember, WorkspaceMember]]]:
    """(옮겨 갈 멤버, 합쳐질 짝). 양쪽에 다 있는 사람은 줄이 하나로 준다."""
    here = list(
        db.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id == source.id))
    )
    there = {
        row.user_id: row
        for row in db.scalars(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == target.id)
        )
    }
    moving = [row for row in here if row.user_id not in there]
    merging = [(row, there[row.user_id]) for row in here if row.user_id in there]
    return moving, merging


def _check_target(source: Workspace, target: Workspace) -> None:
    if target.id == source.id:
        raise AppError(
            "TSC-WORKSPACES-0007",
            "같은 부서로는 옮길 수 없습니다.",
            status=400,
        )


def _reassign(db: Session, *, source: Workspace, target: Workspace) -> dict[str, int]:
    """이 부서의 것을 전부 대상 부서로 옮긴다. 옮긴 수를 돌려준다(감사에 적는다)."""
    moved = {
        "equipment": _move(db, Equipment, Equipment.owner_workspace_id, source, target),
        "reliability_tests": _move(
            db, ReliabilityTest, ReliabilityTest.workspace_id, source, target
        ),
        "spec_documents": _move(db, SpecDocument, SpecDocument.workspace_id, source, target),
        "test_methods": _move(db, TestMethod, TestMethod.owner_workspace_id, source, target),
    }

    # **멤버는 합친다.** 양쪽에 다 있으면 강한 역할을 남긴다 — 옮기다가 권한을 뺏으면
    # 그 사람은 어제 하던 일을 오늘 못 한다.
    moving, merging = _members_to_move(db, source, target)
    for row in moving:
        row.workspace_id = target.id
    for row, twin in merging:
        if row.role == "manager" and twin.role != "manager":
            twin.role = "manager"
        db.delete(row)
    moved["workspace_members"] = len(moving)

    # **하위 부서는 대상 아래로 들어간다.** 대상이 제 자식이면 먼저 올린다 — 안 그러면
    # 그 부서가 제 부모가 된다(고리가 생기면 조직도가 통째로 안 그려진다).
    children = _children_to_move(db, source, target)
    if _lifts_target(db, source, target):
        target.parent_id = source.parent_id
        db.flush()
    for child in children:
        child.parent_id = target.id
    moved["workspaces"] = len(children)

    # 사람의 소속과 가입 신청도 따라간다 — 안 옮기면 로그인한 사람이 없는 부서를
    # 가리킨 채로 남는다(SET NULL 이라 조용히 빈다).
    users = 0
    for user in db.scalars(select(User).where(User.home_workspace_id == source.id)):
        user.home_workspace_id = target.id
        users += 1
    for user in db.scalars(select(User).where(User.requested_workspace_id == source.id)):
        user.requested_workspace_id = target.id
    moved["users"] = users

    db.flush()
    return {key: value for key, value in moved.items() if value}


def _move(db: Session, model: Any, column: Any, source: Workspace, target: Workspace) -> int:
    rows = list(db.scalars(select(model).where(column == source.id)))
    for row in rows:
        setattr(row, column.key, target.id)
    return len(rows)


def delete(db: Session, *, slug: str, actor: User, reassign_to: str | None = None) -> None:
    """부서를 지운다. **가진 것이 있으면 어디로 보낼지 말해야 한다.**

    `reassign_to` 가 없으면 예전 그대로다 — 막는 참조가 하나라도 있으면 거절한다.
    보관(`is_active=false`)이 여전히 기본 수단이고, 맨삭제는 잘못 만든 부서처럼 자료가
    아예 없는 경우를 위한 것이다.

    `reassign_to` 를 주면 **한 걸음으로** 옮기고 지운다. 옮기기와 지우기를 두 번에
    나누면 그 사이에 반쯤 옮겨진 부서가 남고, 그때 무엇이 어디 있는지 아무도 모른다.
    """
    workspace = workspace_by_slug(db, slug)
    if reassign_to:
        target = workspace_by_slug(db, reassign_to)
        _check_target(workspace, target)
        clashes = _clashes(db, workspace, target)
        if clashes:
            # **우리가 고르지 않는다.** 둘 중 무엇을 남길지는 사람이 정할 일이다.
            detail = " · ".join(
                f"{one.label} {', '.join(one.values[:5])}"
                + ("…" if len(one.values) > 5 else "")
                for one in clashes
            )
            raise Conflict(
                "TSC-WORKSPACES-0008",
                f"옮기면 이름이 겹칩니다({detail}). 먼저 한쪽을 고치십시오.",
                details={"clashes": [one.model_dump() for one in clashes]},
            )
        moved = _reassign(db, source=workspace, target=target)
        audit.record(
            db,
            action=audit.WORKSPACE_MERGED,
            actor=actor,
            target_table="workspaces",
            target_id=workspace.id,
            target_label=workspace.name,
            changes={"reassigned_to": target.slug, "moved": moved},
        )
    else:
        blocking = [one for one in references(db, slug=slug) if one.blocks_delete]
        if blocking:
            detail = ", ".join(f"{one.label} {one.count}건" for one in blocking)
            raise Conflict(
                "TSC-WORKSPACES-0006",
                f"이 부서를 가리키는 것이 남아 있습니다({detail}). "
                "먼저 옮기거나 정리하십시오.",
            )
    audit.record(
        db,
        action=audit.WORKSPACE_DELETED,
        actor=actor,
        target_table="workspaces",
        target_id=workspace.id,
        target_label=workspace.name,
    )
    db.delete(workspace)
    db.commit()


# --- 멤버 --------------------------------------------------------------------


def members(db: Session, *, workspace: Workspace) -> list[MemberOut]:
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace.id)
        .order_by(User.display_name)
    ).all()
    return [
        MemberOut(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            role=member.role,
            joined_at=member.created_at,
        )
        for member, user in rows
    ]


def _member_out(db: Session, member: WorkspaceMember) -> MemberOut:
    user = db.get(User, member.user_id)
    if user is None:  # pragma: no cover - FK 가 막는다
        raise NotFound("TSC-WORKSPACES-0007", "계정을 찾을 수 없습니다.")
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        role=member.role,
        joined_at=member.created_at,
    )


def add_member(db: Session, *, workspace: Workspace, email: str, role: str) -> MemberOut:
    if role not in ROLES:
        raise AppError("TSC-WORKSPACES-0008", f"모르는 역할입니다: {role}", status=400)

    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise NotFound("TSC-WORKSPACES-0009", f"그 아이디의 계정이 없습니다: {email}")

    existing = membership_of(db, workspace_id=workspace.id, user_id=user.id)
    if existing is not None:
        raise Conflict("TSC-WORKSPACES-0010", "이미 이 부서의 멤버입니다.")

    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


def set_role(db: Session, *, workspace: Workspace, user_id: uuid.UUID, role: str) -> MemberOut:
    if role not in ROLES:
        raise AppError("TSC-WORKSPACES-0008", f"모르는 역할입니다: {role}", status=400)

    member = membership_of(db, workspace_id=workspace.id, user_id=user_id)
    if member is None:
        raise NotFound("TSC-WORKSPACES-0011", "이 부서의 멤버가 아닙니다.")

    # **마지막 관리자를 강등하지 않는다.** 그러면 그 부서는 아무도 못 고치는
    # 상태가 되고, 복구는 시스템 관리자를 찾아가는 길밖에 없다.
    if (
        member.role == "manager"
        and role != "manager"
        and _manager_count(db, workspace.id) <= 1
    ):
        raise Conflict(
            "TSC-WORKSPACES-0012",
            "부서의 마지막 관리자입니다. 다른 사람을 관리자로 올린 뒤에 바꾸십시오.",
        )

    member.role = role
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


def _manager_count(db: Session, workspace_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "manager",
            )
        )
        or 0
    )


def remove_member(db: Session, *, workspace: Workspace, user_id: uuid.UUID) -> None:
    member = membership_of(db, workspace_id=workspace.id, user_id=user_id)
    if member is None:
        raise NotFound("TSC-WORKSPACES-0011", "이 부서의 멤버가 아닙니다.")
    if member.role == "manager" and _manager_count(db, workspace.id) <= 1:
        raise Conflict(
            "TSC-WORKSPACES-0012",
            "부서의 마지막 관리자입니다. 다른 사람을 관리자로 올린 뒤에 빼십시오.",
        )
    db.delete(member)
    db.commit()


# --- 내보내기 ----------------------------------------------------------------

#: ReportArchive 의 부서 정보 CSV 와 **컬럼도 순서도 같다.**
#:
#: 순서까지 맞추는 이유: 사람이 엑셀에서 두 파일을 나란히 놓고 본다. 한 칸이라도
#: 어긋나면 그 대조는 눈으로 못 한다.
EXPORT_HEADER = (
    "slug",
    "name",
    "parent_slug",
    "parent_name",
    "depth",
    "path",
    "kind",
    "status",
    "description",
    "sort_order",
    "external_view_default",
    "member_count",
    "managers",
    "created_at",
)


def export_rows(db: Session) -> list[list[object]]:
    """부서 정보를 CSV 행으로. **트리 순서 그대로** — 화면과 같은 순서다.

    ## 우리가 모르는 칸은 아는 척하지 않는다

    `kind` 는 전부 `org` 다 — 이쪽에는 집계 노드도 한시 조직도 없다.
    `external_view_default` 는 **비운다.** 이쪽 `restricted` 는 장비 가시성이라
    저쪽의 보고서 공개 정책과 다른 물음이고, 채워 보내면 그 값이 저쪽에서 정책이
    된다(ADR 없이 정해질 일이 아니다).
    """
    rows = ordered_tree(db)
    by_id = {row.id: row for row, _, _ in rows}

    counts = {
        workspace_id: int(total)
        for workspace_id, total in db.execute(
            select(WorkspaceMember.workspace_id, func.count(WorkspaceMember.id)).group_by(
                WorkspaceMember.workspace_id
            )
        )
    }
    managers: dict[uuid.UUID, list[str]] = {}
    for workspace_id, label in db.execute(
        select(WorkspaceMember.workspace_id, User.display_name)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.role == "manager")
        .order_by(User.display_name)
    ):
        managers.setdefault(workspace_id, []).append(label)

    out: list[list[object]] = []
    for workspace, depth, path in rows:
        parent = by_id.get(workspace.parent_id) if workspace.parent_id else None
        out.append(
            [
                workspace.slug,
                workspace.name,
                parent.slug if parent else "",
                parent.name if parent else "",
                depth,
                # 저쪽은 " > " 로 잇는다. 우리 화면은 " / " 지만 **내보내는 파일은
                # 받는 쪽 규약을 따른다.**
                path.replace(" / ", " > "),
                "org",
                "active" if workspace.is_active else "archived",
                workspace.description or "",
                workspace.sort_order,
                "",
                counts.get(workspace.id, 0),
                "; ".join(managers.get(workspace.id, [])),
                workspace.created_at.isoformat() if workspace.created_at else "",
            ]
        )
    return out
