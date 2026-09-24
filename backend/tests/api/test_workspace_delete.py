"""부서 삭제와 이관 — **가진 것이 있으면 어디로 보낼지 말해야 한다.**

조직은 개편된다. 팀이 본부에 합쳐지고 본부가 없어지는데, 그때 그 부서의 장비 수십 대와
신뢰성 시험과 규격서가 함께 사라지면 안 된다. 그래서 삭제는 둘 중 하나다:

1. **맨삭제** — 가리키는 것이 하나도 없을 때만. 잘못 만든 부서를 위한 길이다.
2. **이관 삭제** — 가진 것을 다른 부서로 옮기고 지운다. 한 걸음이다(둘로 나누면 그
   사이에 반쯤 옮겨진 부서가 남고, 그때 무엇이 어디 있는지 아무도 모른다).

여기서 지키는 것:

* **세는 자리와 막는 자리가 같다.** 신뢰성 시험·사내 규격서는 나중에 생긴 표인데 세는
  목록에 없었다 — 그 상태로 지우면 DB 가 막아 500 이 났다(원인이 안 적힌 오류).
* **누르기 전에 답한다.** 무엇이 옮겨지고 무엇이 겹치는지 미리 본다.
* **겹치면 우리가 고르지 않는다.** 둘 중 무엇을 남길지는 사람이 정할 일이다.
* **고리를 만들지 않는다.** 대상이 제 자식이면 먼저 올린다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.audit.models import AuditEntry
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _team(client: TestClient, admin: Signed, *, parent: str | None = None) -> str:
    made = client.post(
        "/api/workspaces",
        json={
            "slug": f"t-{uuid.uuid4().hex[:8]}",
            "name": f"팀-{uuid.uuid4().hex[:4]}",
            "parent_slug": parent,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["slug"])


def _equipment(client: TestClient, admin: Signed, slug: str, **extra: Any) -> Response:
    payload: dict[str, Any] = {
        "asset_no": f"EQ-{uuid.uuid4().hex[:6]}",
        "name": "인장시험기",
        "workspace_slug": slug,
        "site_term_id": site_id(client, admin),
        "category_term_id": category_id(client, admin),
        "location": "3동 201호",
        **extra,
    }
    made: Response = client.post("/api/equipment", json=payload, headers=admin.headers)
    assert made.status_code == 201, made.text
    return made


def _reliability(client: TestClient, admin: Signed, slug: str, name: str) -> Response:
    made: Response = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": slug, "name": name},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return made


def _document(client: TestClient, admin: Signed, slug: str, code: str) -> Response:
    made: Response = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": code, "title": "환경 시험 표준"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return made


def _references(client: TestClient, admin: Signed, slug: str) -> dict[str, dict[str, Any]]:
    got = client.get(f"/api/workspaces/{slug}/references", headers=admin.headers)
    assert got.status_code == 200, got.text
    return {one["table"]: one for one in got.json()}


def test_신뢰성_시험과_규격서도_세고_막는다(client: TestClient, admin: Signed) -> None:
    """**세는 자리와 막는 자리는 같아야 한다.**

    두 표는 나중에 생겼는데 세는 목록에 없었다. 그래서 시험이 있는 부서를 지우면 DB 의
    외래키가 막아 500 이 났다 — 화면에 뜨는 것은 원인이 안 적힌 오류이고, 사람은 무엇을
    먼저 치워야 하는지 알 수 없었다.
    """
    team = _team(client, admin)
    _reliability(client, admin, team, f"고온고습-{uuid.uuid4().hex[:6]}")
    _document(client, admin, team, f"MX-{uuid.uuid4().hex[:6]}")

    seen = _references(client, admin, team)
    assert seen["reliability_tests"]["count"] == 1
    assert seen["reliability_tests"]["blocks_delete"] is True
    assert seen["spec_documents"]["count"] == 1

    blocked = client.delete(f"/api/workspaces/{team}", headers=admin.headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-WORKSPACES-0006"
    # **무엇이 남아 있는지 말한다** — 「지울 수 없습니다」 만으로는 치울 수가 없다.
    assert "신뢰성 시험" in blocked.json()["error"]["message"]


def test_이관하면_가진_것이_전부_따라간다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """장비·시험·규격서·시험법·멤버·하위 부서·사람의 소속까지 한 걸음에."""
    gone = _team(client, admin)
    stays = _team(client, admin)
    child = _team(client, admin, parent=gone)

    equipment = _equipment(client, admin, gone).json()
    test = _reliability(client, admin, gone, f"열충격-{uuid.uuid4().hex[:6]}").json()
    document = _document(client, admin, gone, f"MX-{uuid.uuid4().hex[:6]}").json()
    method = client.post(
        "/api/methods",
        json={
            "code": f"MX-M-{uuid.uuid4().hex[:6]}",
            "title": "사내 시험법",
            "workspace_slug": gone,
        },
        headers=admin.headers,
    )
    assert method.status_code == 201, method.text

    # 그 부서에만 속한 사람 하나 — 소속이 빈 채로 남으면 로그인해도 갈 곳이 없다.
    email = f"one-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw"),
        display_name="한 사람",
        status="active",
        home_workspace_id=db.scalar(select(Workspace.id).where(Workspace.slug == gone)),
    )
    db.add(user)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=db.scalar(select(Workspace.id).where(Workspace.slug == gone)),
            user_id=user.id,
            role="manager",
        )
    )
    db.commit()

    # **누르기 전에 무엇이 옮겨지는지 본다.**
    preview = client.get(
        f"/api/workspaces/{gone}/reassign-preview",
        params={"to": stays},
        headers=admin.headers,
    )
    assert preview.status_code == 200, preview.text
    moves = {one["table"]: one["count"] for one in preview.json()["moves"]}
    assert moves["equipment"] == 1 and moves["reliability_tests"] == 1
    assert moves["spec_documents"] == 1 and moves["workspaces"] == 1
    assert preview.json()["clashes"] == []

    dropped = client.delete(
        f"/api/workspaces/{gone}", params={"reassign_to": stays}, headers=admin.headers
    )
    assert dropped.status_code == 204, dropped.text

    # 부서는 없고, 가진 것은 전부 옮겨 가 있다.
    assert (
        client.get(f"/api/workspaces/{gone}/references", headers=admin.headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/equipment/{equipment['id']}", headers=admin.headers).json()[
            "workspace_slug"
        ]
        == stays
    )
    moved_test = client.get(f"/api/reliability-tests/{test['id']}", headers=admin.headers)
    assert moved_test.json()["workspace_slug"] == stays
    moved_doc = client.get(f"/api/spec-documents/{document['id']}", headers=admin.headers)
    assert moved_doc.json()["workspace_slug"] == stays
    assert (
        client.get(f"/api/methods/{method.json()['id']}", headers=admin.headers).json()[
            "workspace_slug"
        ]
        == stays
    )

    # 하위 부서는 대상 아래로, 사람의 소속도 따라간다.
    kept = db.scalar(select(Workspace).where(Workspace.slug == child))
    target = db.scalar(select(Workspace).where(Workspace.slug == stays))
    assert kept is not None and target is not None
    assert kept.parent_id == target.id
    db.refresh(user)
    assert user.home_workspace_id == target.id

    # **누가 무엇을 어디로 보냈는지 남는다.**
    merged = db.scalars(
        select(AuditEntry)
        .where(AuditEntry.action == "workspace.merged")
        .order_by(AuditEntry.created_at.desc())
    ).first()
    assert merged is not None
    assert merged.changes["reassigned_to"] == stays
    assert merged.changes["moved"]["equipment"] == 1


def test_옮기면_이름이_겹치는_것을_먼저_말한다(client: TestClient, admin: Signed) -> None:
    """**우리가 고르지 않는다.** 둘 중 무엇을 남길지는 사람이 정할 일이다."""
    gone = _team(client, admin)
    stays = _team(client, admin)
    name = f"고온고습 1000h-{uuid.uuid4().hex[:6]}"
    _reliability(client, admin, gone, name)
    _reliability(client, admin, stays, name)

    asset = f"A-{uuid.uuid4().hex[:6]}"
    _equipment(client, admin, gone, dept_asset_no=asset)
    _equipment(client, admin, stays, dept_asset_no=asset)

    preview = client.get(
        f"/api/workspaces/{gone}/reassign-preview",
        params={"to": stays},
        headers=admin.headers,
    )
    clashes = {one["table"]: one["values"] for one in preview.json()["clashes"]}
    assert clashes["reliability_tests"] == [name]
    assert clashes["equipment"] == [asset]

    blocked = client.delete(
        f"/api/workspaces/{gone}", params={"reassign_to": stays}, headers=admin.headers
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-WORKSPACES-0008"
    # 값까지 말한다 — 「겹칩니다」 만으로는 무엇을 고칠지 모른다.
    assert name in blocked.json()["error"]["message"]


def test_규격서_번호는_대소문자를_같은_것으로_본다(client: TestClient, admin: Signed) -> None:
    """등록이 대소문자를 무시하고 거절하므로, 이관도 같은 눈으로 봐야 한다 — 안 그러면
    DB 는 받아 주는데 화면에서는 「같은 번호가 둘」 이 된다."""
    gone = _team(client, admin)
    stays = _team(client, admin)
    code = f"MX-REL-{uuid.uuid4().hex[:6]}"
    _document(client, admin, gone, code.lower())
    _document(client, admin, stays, code.upper())

    preview = client.get(
        f"/api/workspaces/{gone}/reassign-preview",
        params={"to": stays},
        headers=admin.headers,
    )
    clashes = {one["table"]: one["values"] for one in preview.json()["clashes"]}
    assert clashes["spec_documents"] == [code.lower()]


def test_멤버는_합치고_강한_역할을_남긴다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """옮기다가 권한을 뺏으면 그 사람은 어제 하던 일을 오늘 못 한다."""
    gone = _team(client, admin)
    stays = _team(client, admin)
    email = f"both-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw"),
        display_name="양쪽 사람",
        status="active",
    )
    db.add(user)
    db.commit()

    for slug, role in ((gone, "manager"), (stays, "member")):
        added = client.post(
            f"/api/workspaces/{slug}/members",
            json={"email": email, "role": role},
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text

    dropped = client.delete(
        f"/api/workspaces/{gone}", params={"reassign_to": stays}, headers=admin.headers
    )
    assert dropped.status_code == 204, dropped.text

    rows = client.get(f"/api/workspaces/{stays}/members", headers=admin.headers).json()
    mine = [one for one in rows if one["email"] == email]
    assert len(mine) == 1, "한 부서에 같은 사람이 둘일 수는 없다"
    assert mine[0]["role"] == "manager", "강한 역할이 남아야 한다"


def test_대상이_제_자식이면_먼저_올린다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """본부를 없애고 그 아래 팀 하나로 합치는 일은 흔하다. 그대로 두면 그 팀이 제 부모가
    되고, 고리가 생기면 조직도가 통째로 안 그려진다."""
    top = _team(client, admin)
    head = _team(client, admin, parent=top)
    keep = _team(client, admin, parent=head)
    sibling = _team(client, admin, parent=head)

    dropped = client.delete(
        f"/api/workspaces/{head}", params={"reassign_to": keep}, headers=admin.headers
    )
    assert dropped.status_code == 204, dropped.text

    rows = {row.slug: row for row in db.scalars(select(Workspace))}
    db.refresh(rows[keep])
    db.refresh(rows[sibling])
    # 대상은 없어진 부서의 자리로 올라가고, 형제는 그 아래로 들어간다.
    assert rows[keep].parent_id == rows[top].id
    assert rows[sibling].parent_id == rows[keep].id


def test_같은_부서로는_못_옮긴다(client: TestClient, admin: Signed) -> None:
    team = _team(client, admin)
    same = client.delete(
        f"/api/workspaces/{team}", params={"reassign_to": team}, headers=admin.headers
    )
    assert same.status_code == 400, same.text
    assert same.json()["error"]["code"] == "TSC-WORKSPACES-0007"

    missing = client.delete(
        f"/api/workspaces/{team}",
        params={"reassign_to": "없는부서"},
        headers=admin.headers,
    )
    assert missing.status_code == 404, missing.text


def test_지우는_것은_시스템_관리자뿐(client: TestClient, admin: Signed, db: Session) -> None:
    """부서를 지우는 것은 **전사에 영향**을 준다 — 부서 관리자가 할 일이 아니다."""
    team = _team(client, admin)
    email = f"mgr-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw"),
        display_name="부서 관리자",
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=db.scalar(select(Workspace.id).where(Workspace.slug == team)),
            user_id=user.id,
            role="manager",
        )
    )
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw"})
    headers = {"Authorization": f"Bearer {token.json()['access_token']}"}

    assert client.delete(f"/api/workspaces/{team}", headers=headers).status_code == 403
    assert (
        client.get(
            f"/api/workspaces/{team}/reassign-preview",
            params={"to": admin.workspace},
            headers=headers,
        ).status_code
        == 403
    )
