"""소속 바꾸기 — **한 번에 바꾼다.**

부서를 옮기는 일은 「떼고 붙이기」 두 걸음인데, 두 번에 나누면 그 사이에 **아무 데도 안
속한 사람**이 남는다. 두 번째가 실패하면 그 상태로 굳고, 그 사람은 로그인해도 갈 곳이
없으면서 무엇이 잘못됐는지도 모른다.

여기서 지키는 것:

1. 준 목록이 **곧 소속**이다 — 있던 것은 지운다.
2. **대표 소속이 따라간다.** 뺀 부서가 대표였으면 남은 것으로 옮기고, 남은 것이 없으면
   비운다 — 소속이 아닌 부서를 대표로 두면 로그인하자마자 403 이 난다.
3. **시스템 관리자만** 한다. 부서 관리자는 제 부서 멤버만 다룬다.
4. 누가 어디서 어디로 옮겼는지 **감사에 남는다.**
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.audit.models import AuditEntry
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed


def _team(client: TestClient, admin: Signed, name: str) -> str:
    made = client.post(
        "/api/workspaces",
        json={"slug": f"t-{uuid.uuid4().hex[:8]}", "name": name},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["slug"])


def _person(client: TestClient, db: Session, slug: str) -> User:
    email = f"one-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw"),
        display_name="한 사람",
        status="active",
    )
    db.add(user)
    db.flush()
    workspace = db.scalar(select(Workspace).where(Workspace.slug == slug))
    assert workspace is not None
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    user.home_workspace_id = workspace.id
    db.commit()
    db.refresh(user)
    return user


def _set(client: TestClient, who: Signed, user_id: Any, items: list[dict[str, str]]) -> Any:
    return client.put(
        f"/api/accounts/{user_id}/memberships",
        json={"items": items},
        headers=who.headers,
    )


def test_소속을_한_번에_옮긴다(client: TestClient, admin: Signed, db: Session) -> None:
    here = _team(client, admin, "떠날팀")
    there = _team(client, admin, "갈팀")
    user = _person(client, db, here)

    moved = _set(client, admin, user.id, [{"workspace_slug": there, "role": "manager"}])
    assert moved.status_code == 200, moved.text
    assert moved.json()["memberships"] == [there] or there in str(moved.json()["memberships"])

    db.refresh(user)
    rows = list(db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)))
    assert len(rows) == 1, "있던 소속은 지운다"
    assert rows[0].role == "manager"

    # **대표 소속이 따라간다** — 안 따라가면 로그인하자마자 403 이다.
    target = db.scalar(select(Workspace).where(Workspace.slug == there))
    assert target is not None and user.home_workspace_id == target.id


def test_둘_이상도_되고_역할이_갈린다(client: TestClient, admin: Signed, db: Session) -> None:
    one = _team(client, admin, "첫팀")
    two = _team(client, admin, "둘째팀")
    user = _person(client, db, one)

    done = _set(
        client,
        admin,
        user.id,
        [
            {"workspace_slug": one, "role": "manager"},
            {"workspace_slug": two, "role": "member"},
        ],
    )
    assert done.status_code == 200, done.text
    rows = {
        db.get(Workspace, row.workspace_id).slug: row.role  # type: ignore[union-attr]
        for row in db.scalars(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
        )
    }
    assert rows == {one: "manager", two: "member"}


def test_비우면_대표_소속도_함께_비운다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """내보내는 일은 실제로 있다. 그때 대표만 남으면 **없는 소속을 가리킨 채**로 남는다."""
    here = _team(client, admin, "나갈팀")
    user = _person(client, db, here)

    emptied = _set(client, admin, user.id, [])
    assert emptied.status_code == 200, emptied.text
    db.refresh(user)
    assert user.home_workspace_id is None
    assert db.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)) is None


def test_없는_부서와_모르는_역할은_거절한다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    here = _team(client, admin, "그대로팀")
    user = _person(client, db, here)

    missing = _set(client, admin, user.id, [{"workspace_slug": "없는부서"}])
    assert missing.status_code == 404, missing.text

    wrong = _set(client, admin, user.id, [{"workspace_slug": here, "role": "사장"}])
    assert wrong.status_code == 422, wrong.text

    # **거절했으면 아무것도 안 바뀌어야 한다.**
    db.refresh(user)
    rows = list(db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)))
    assert len(rows) == 1 and rows[0].role == "member"


def test_부서_관리자는_못_한다(client: TestClient, admin: Signed, db: Session) -> None:
    """소속을 옮기는 것은 **전사의 일**이다 — 제 부서로 사람을 끌어올 수 있으면 안 된다."""
    here = _team(client, admin, "관리자팀")
    user = _person(client, db, here)

    email = f"mgr-{uuid.uuid4().hex[:8]}@testscope.local"
    manager = User(
        email=email,
        password_hash=security.hash_password("pw"),
        display_name="부서 관리자",
        status="active",
    )
    db.add(manager)
    db.flush()
    workspace = db.scalar(select(Workspace).where(Workspace.slug == here))
    assert workspace is not None
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=manager.id, role="manager"))
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw"})
    signed = Signed(email=email, token=token.json()["access_token"], workspace=here)

    refused = _set(client, signed, user.id, [])
    assert refused.status_code == 403, refused.text


def test_누가_어디서_어디로_옮겼는지_남는다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    here = _team(client, admin, "전팀")
    there = _team(client, admin, "후팀")
    user = _person(client, db, here)
    _set(client, admin, user.id, [{"workspace_slug": there}])

    entry = db.scalars(
        select(AuditEntry)
        .where(AuditEntry.action == "account.memberships_changed")
        .order_by(AuditEntry.created_at.desc())
    ).first()
    assert entry is not None
    assert entry.changes["memberships"]["before"] == [here]
    assert entry.changes["memberships"]["after"] == [there]


def test_지금_소속을_역할과_함께_준다(client: TestClient, admin: Signed, db: Session) -> None:
    """**목록은 slug 만 준다.** 그것만 보고 창을 채우면 역할을 모르는 채로 되보내게 되고,
    그러면 부서 관리자가 조용히 멤버로 내려앉는다 — 그 사람은 어제 하던 일을 오늘 못
    하면서 왜인지도 모른다(2026-09-28 실측).
    """
    one = _team(client, admin, "관리팀")
    two = _team(client, admin, "참여팀")
    user = _person(client, db, one)
    _set(
        client,
        admin,
        user.id,
        [
            {"workspace_slug": one, "role": "manager"},
            {"workspace_slug": two, "role": "member"},
        ],
    )

    got = client.get(f"/api/accounts/{user.id}/memberships", headers=admin.headers)
    assert got.status_code == 200, got.text
    rows = {row["workspace_slug"]: row for row in got.json()}
    assert rows[one]["role"] == "manager"
    assert rows[two]["role"] == "member"
    # 이름도 함께 — 창이 slug 말고 사람이 아는 이름을 보여야 한다.
    assert rows[one]["workspace_name"] == "관리팀"


def test_부서가_쉰이_넘어도_저장된다(client: TestClient, admin: Signed, db: Session) -> None:
    """한도를 50으로 뒀다가 **부서가 쉰이 넘는 곳에서 막혔다** — 전사 관리자는 모든
    부서에 속한다. 조직도만큼은 받아야 한다."""
    user = _person(client, db, _team(client, admin, "첫팀"))
    slugs = [_team(client, admin, f"팀{index}") for index in range(55)]

    done = _set(client, admin, user.id, [{"workspace_slug": one} for one in slugs])
    assert done.status_code == 200, done.text
    assert (
        len(client.get(f"/api/accounts/{user.id}/memberships", headers=admin.headers).json())
        == 55
    )
