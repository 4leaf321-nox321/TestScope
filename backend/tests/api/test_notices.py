"""공지 — **초안은 관리자만 보고, 게시는 따로 누른다.**

여기서 지키는 것 — 초안은 목록에도 팝업에도 안 나온다(관리자가 물을 때만) · 게시하면
모두에게 보이고 팝업이면 스스로 뜬다 · 두 번 게시하면 409(게시 시각이 「언제 알렸나」 의
근거다) · 고치기는 안 보낸 칸을 안 바꾸고 게시 여부도 안 바꾼다 · 쓰는 것은 시스템 관리자만.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed


def _member(client: TestClient, db: Session, workspace: Workspace) -> Signed:
    email = f"member-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-member"),
        display_name="부서원",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw-member"})
    return Signed(email=email, token=token.json()["access_token"], workspace=workspace.slug)


def _ids(client: TestClient, who: Signed, url: str) -> set[str]:
    got = client.get(url, headers=who.headers)
    assert got.status_code == 200, got.text
    return {one["id"] for one in got.json()}


def test_초안은_관리자만_보고_게시하면_모두에게_뜬다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    member = _member(client, db, workspace)
    made = client.post(
        "/api/notices",
        json={
            "title": f"점검 안내-{uuid.uuid4().hex[:6]}",
            "body": "토요일 오전 서버를 내립니다.",
            "is_popup": True,
            "publish": False,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    draft: dict[str, Any] = made.json()
    assert draft["published_at"] is None

    # 반쯤 쓴 글이 전사에 보이면 그 자체가 사고다 — 목록에도 팝업에도 없다.
    assert draft["id"] not in _ids(client, member, "/api/notices")
    assert draft["id"] not in _ids(client, member, "/api/notices/popup")
    # 관리자는 물을 때만 본다(일반 목록과 같은 모양을 지키려고).
    assert draft["id"] in _ids(client, admin, "/api/notices?include_drafts=true")
    # 관리자가 아니면 물어도 안 나온다.
    assert draft["id"] not in _ids(client, member, "/api/notices?include_drafts=true")

    published = client.post(f"/api/notices/{draft['id']}/publish", headers=admin.headers)
    assert published.status_code == 200, published.text
    assert published.json()["published_at"] is not None
    assert draft["id"] in _ids(client, member, "/api/notices")
    assert draft["id"] in _ids(client, member, "/api/notices/popup")

    # 두 번 게시하면 게시 시각이 옮겨진다 — 그 시각은 「언제 알렸나」 의 근거다.
    again = client.post(f"/api/notices/{draft['id']}/publish", headers=admin.headers)
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "TSC-NOTICES-0002"


def test_고치기는_보낸_칸만_바꾸고_게시_여부는_안_바꾼다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    made = client.post(
        "/api/notices",
        json={"title": "초안 제목", "body": "초안 내용", "publish": False},
        headers=admin.headers,
    ).json()
    fixed = client.patch(
        f"/api/notices/{made['id']}", json={"title": "고친 제목"}, headers=admin.headers
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["title"] == "고친 제목"
    assert fixed.json()["body"] == "초안 내용"
    # 저장 단추 하나로 전사에 나가면 안 된다 — 고쳐도 초안은 초안이다.
    assert fixed.json()["published_at"] is None

    # 제목을 비울 수는 없다.
    empty = client.patch(
        f"/api/notices/{made['id']}", json={"title": ""}, headers=admin.headers
    )
    assert empty.status_code == 422, empty.text

    # 쓰는 것은 시스템 관리자만.
    member = _member(client, db, workspace)
    for refused in (
        client.patch(
            f"/api/notices/{made['id']}", json={"title": "x"}, headers=member.headers
        ),
        client.post(f"/api/notices/{made['id']}/publish", headers=member.headers),
    ):
        assert refused.status_code == 403, refused.text
