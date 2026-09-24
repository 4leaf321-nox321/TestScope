"""계정 로직 — 계정 자체의 생애(생성·승인·정지·삭제).

부서 단위 멤버 관리는 workspaces 모듈이 한다. 두 책임을 섞으면 화면도 섞인다.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import USER_STATUSES, User
from app.modules.accounts.schemas import AccountOut
from app.modules.auth import security
from app.modules.notifications import rules
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.permissions import workspace_by_slug


def _now() -> datetime:
    return datetime.now(UTC)


def account_out(db: Session, user: User) -> AccountOut:
    slugs = list(
        db.scalars(
            select(Workspace.slug)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
            .order_by(Workspace.name)
        )
    )
    home = db.get(Workspace, user.home_workspace_id) if user.home_workspace_id else None
    requested = (
        db.get(Workspace, user.requested_workspace_id) if user.requested_workspace_id else None
    )
    return AccountOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        is_system_admin=user.is_system_admin,
        must_change_password=user.must_change_password,
        home_workspace_slug=home.slug if home else None,
        requested_workspace_slug=requested.slug if requested else None,
        memberships=slugs,
        created_at=user.created_at,
        decided_at=user.decided_at,
        decision_note=user.decision_note,
    )


def active_system_admin_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.is_system_admin.is_(True),
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        or 0
    )


def pending_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.status == "pending", User.deleted_at.is_(None))
        )
        or 0
    )


def get_account(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("TSC-ACCOUNTS-0001", "계정을 찾을 수 없습니다.")
    return user


def list_accounts(db: Session, *, status: str | None, limit: int, offset: int) -> list[User]:
    query = select(User).where(User.deleted_at.is_(None))
    if status is not None:
        query = query.where(User.status == status)
    # 승인 대기가 먼저 온다. **관리자가 할 일이 목록 맨 위에 있어야 한다** —
    # 이름순으로 두면 대기 하나를 찾으려고 세 쪽을 넘겨야 한다.
    return list(
        db.scalars(
            query.order_by((User.status != "pending"), User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def signup(
    db: Session, *, email: str, password: str, display_name: str, workspace_slug: str
) -> User:
    """가입 신청. 승인 전까지는 로그인할 수 없다(status=pending)."""
    normalized = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise Conflict("TSC-ACCOUNTS-0002", "이미 있는 아이디입니다.")

    workspace = workspace_by_slug(db, workspace_slug)
    user = User(
        email=normalized,
        password_hash=security.hash_password(password),
        display_name=display_name.strip(),
        status="pending",
        requested_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    # 승인할 사람에게 알린다 — 홈의 「남은 일」 은 들어가야 보인다.
    rules.signup_requested(db, user)
    db.commit()
    db.refresh(user)
    return user


def create_account(
    db: Session,
    *,
    email: str,
    display_name: str,
    workspace_slug: str,
    role: str,
    is_system_admin: bool,
    created_by: User,
) -> tuple[User, str]:
    """관리자가 계정을 만든다. 임시 비밀번호를 함께 돌려준다."""
    normalized = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise Conflict("TSC-ACCOUNTS-0002", "이미 있는 아이디입니다.")

    workspace = workspace_by_slug(db, workspace_slug)
    temporary = secrets.token_urlsafe(9)
    user = User(
        email=normalized,
        password_hash=security.hash_password(temporary),
        display_name=display_name.strip(),
        status="active",
        is_system_admin=is_system_admin,
        home_workspace_id=workspace.id,
        # **첫 로그인 때 바꾸게 한다.** 임시 비밀번호가 그대로 남는 것이 가장
        # 흔한 사고이고, 그 사고는 계정을 만든 사람이 아니라 몇 달 뒤에 드러난다.
        must_change_password=True,
        decided_at=_now(),
        decided_by_id=created_by.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    db.commit()
    db.refresh(user)
    return user, temporary


def approve(
    db: Session,
    *,
    user_id: uuid.UUID,
    decided_by: User,
    workspace_slug: str | None,
    role: str,
) -> User:
    user = get_account(db, user_id)
    if user.status != "pending":
        raise Conflict("TSC-ACCOUNTS-0003", "승인 대기 중인 계정이 아닙니다.")

    slug = workspace_slug
    if slug is None:
        requested = (
            db.get(Workspace, user.requested_workspace_id)
            if user.requested_workspace_id
            else None
        )
        if requested is None:
            raise AppError(
                "TSC-ACCOUNTS-0004",
                "신청한 부서가 없어졌습니다. 배정할 부서를 골라 주십시오.",
                status=400,
            )
        slug = requested.slug

    workspace = workspace_by_slug(db, slug)
    user.status = "active"
    user.decided_at = _now()
    user.decided_by_id = decided_by.id
    # **대표 소속을 여기서 정한다.** 승인은 "어느 부서 사람인가" 를 정하는 자리이고,
    # 비워 두면 로그인이 이름순 첫 부서로 떨어진다 — 사람이 정한 값이 아니다.
    user.home_workspace_id = workspace.id

    if (
        db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user.id,
            )
        )
        is None
    ):
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))

    audit.record(
        db,
        action=audit.ACCOUNT_DECIDED,
        actor=decided_by,
        target_table="users",
        target_id=user.id,
        target_label=user.email,
        workspace_id=workspace.id,
        changes={"status": {"before": "pending", "after": "active"}},
    )
    # 로그인해서 처음 보는 것이 「승인됐다」 여야 한다.
    rules.account_approved(db, user, workspace)
    db.commit()
    db.refresh(user)
    return user


def reject(db: Session, *, user_id: uuid.UUID, decided_by: User, note: str) -> User:
    user = get_account(db, user_id)
    if user.status != "pending":
        raise Conflict("TSC-ACCOUNTS-0003", "승인 대기 중인 계정이 아닙니다.")
    user.status = "suspended"
    user.decided_at = _now()
    user.decided_by_id = decided_by.id
    # **사유를 반드시 남긴다.** 메일이 없어 통보가 앱 안에서만 되므로, 여기 안
    # 적히면 신청한 사람은 왜 거절됐는지 영영 모른다.
    user.decision_note = note
    audit.record(
        db,
        action=audit.ACCOUNT_DECIDED,
        actor=decided_by,
        target_table="users",
        target_id=user.id,
        target_label=user.email,
        changes={"status": {"before": "pending", "after": "suspended"}},
        reason=note,
    )
    db.commit()
    db.refresh(user)
    return user


def _guard_last_admin(db: Session, user: User, *, what: str) -> None:
    """마지막 활성 시스템 관리자를 잃는 길을 막는다.

    잃으면 복구 경로가 **서버 콘솔뿐**이다. 그 상태는 실제로 일어나고, 일어난
    뒤에는 화면에서 할 수 있는 것이 하나도 없다.
    """
    if user.is_system_admin and user.status == "active" and active_system_admin_count(db) <= 1:
        raise Conflict(
            "TSC-ACCOUNTS-0005",
            f"마지막 활성 시스템 관리자입니다. 다른 사람을 지정한 뒤에 {what}십시오.",
        )


def set_status(db: Session, *, user_id: uuid.UUID, status: str, actor: User) -> User:
    if status not in USER_STATUSES:
        raise AppError("TSC-ACCOUNTS-0006", f"모르는 상태입니다: {status}", status=400)
    user = get_account(db, user_id)
    if status != "active":
        _guard_last_admin(db, user, what="정지하")

    before = user.status
    user.status = status
    audit.record(
        db,
        action=audit.ACCOUNT_SUSPENDED,
        actor=actor,
        target_table="users",
        target_id=user.id,
        target_label=user.email,
        changes={"status": {"before": before, "after": status}},
    )
    db.commit()
    db.refresh(user)
    return user


def set_system_admin(db: Session, *, user_id: uuid.UUID, grant: bool, actor: User) -> User:
    user = get_account(db, user_id)
    if not grant:
        _guard_last_admin(db, user, what="해제하")

    before = user.is_system_admin
    user.is_system_admin = grant
    audit.record(
        db,
        action=audit.ACCOUNT_ADMIN_CHANGED,
        actor=actor,
        target_table="users",
        target_id=user.id,
        target_label=user.email,
        changes={"is_system_admin": {"before": before, "after": grant}},
    )
    db.commit()
    db.refresh(user)
    return user


def set_home_workspace(
    db: Session, *, user_id: uuid.UUID, workspace_slug: str, actor: User
) -> User:
    """대표 소속 — 이 사람이 로그인해서 처음 서는 부서."""
    user = get_account(db, user_id)
    workspace = workspace_by_slug(db, workspace_slug)

    # **소속이 아닌 부서를 대표로 둘 수 없다.** 두면 로그인하자마자 403 이 나고,
    # 사람은 그것을 "시스템이 고장났다" 로 읽는다.
    if (
        db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user.id,
            )
        )
        is None
    ):
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))

    before = user.home_workspace_id
    user.home_workspace_id = workspace.id
    audit.record(
        db,
        action=audit.ACCOUNT_HOME_CHANGED,
        actor=actor,
        target_table="users",
        target_id=user.id,
        target_label=user.email,
        workspace_id=workspace.id,
        changes={"home_workspace": {"before": str(before), "after": workspace.slug}},
    )
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, *, user_id: uuid.UUID, actor: User) -> str:
    """임시 비밀번호로 되돌린다. 평문은 **이 응답에서 한 번만** 나온다.

    관리자 복구 경로가 서버 콘솔뿐이면 사람은 결국 DB 를 직접 만진다 — 그 경로가
    강제 변경을 건너뛴다. 화면에 두되 must_change_password 를 함께 켠다.
    """
    user = get_account(db, user_id)
    temporary = secrets.token_urlsafe(9)
    user.password_hash = security.hash_password(temporary)
    user.must_change_password = True
    user.failed_logins = 0
    user.last_failed_login_at = None
    db.commit()
    return temporary


def delete_account(db: Session, *, user_id: uuid.UUID, actor: User) -> User:
    """계정을 지운다. **행은 남고 접근만 끊긴다.**

    장비 담당자·감사 기록이 이 계정을 가리키고 있다. 행을 실제로 지우면 그것들이
    가리킬 곳을 잃고, 몇 년 전 장비를 누가 등록했는지 답할 수 없게 된다.
    """
    user = get_account(db, user_id)
    if user.id == actor.id:
        raise Conflict("TSC-ACCOUNTS-0007", "자기 계정은 지울 수 없습니다.")
    _guard_last_admin(db, user, what="지우")

    user.deleted_at = _now()
    user.status = "suspended"
    audit.record(
        db,
        action=audit.ACCOUNT_DELETED,
        actor=actor,
        target_table="users",
        target_id=user.id,
        target_label=user.email,
    )
    db.commit()
    db.refresh(user)
    return user
