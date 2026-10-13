"""규격 번호를 고친다 — **시스템 관리자만, 옛 번호는 남긴다.**

번호를 고칠 길이 없었다(제목만 고쳐졌다 — 2026-10-13 사용자 보고). 그런데 번호만 바꾸면
번호를 열쇠로 쓰는 곳이 그 규격을 잃는다: 카탈로그 반입은 옛 번호로 같은 규격을 하나 더 만들고,
검토함의 규격 물음은 주인 없는 줄이 되고, 사람은 옛 번호로 검색해 「없음」 을 받는다.

여기서 지키는 것:

1. 시스템 관리자는 번호를 고치고, 옛 번호가 `former_codes` 에 남는다. 그 밖의 사람은 403.
2. 목록 검색 · resolve · 반입(`code_index`)이 옛 번호로도 그 규격을 찾는다.
3. 다른 규격의 번호(같은 판) · 옛 번호와 겹치면 409.
4. 검토함의 규격 물음 줄이 새 번호로 옮겨 간다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from app.shared.text import method_key
from tests.api.conftest import Signed


def _method(client: TestClient, admin: Signed, **extra: Any) -> dict[str, Any]:
    code = f"KS M {uuid.uuid4().hex[:5]}"
    made = client.post(
        "/api/methods",
        json={"code": code, "title": code, **extra},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def test_시스템_관리자는_번호를_고치고_옛_번호로도_찾아온다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.methods.services import code_index

    method = _method(client, admin)
    old = method["code"]
    new = f"KS M ISO {uuid.uuid4().hex[:5]}"

    fixed = client.patch(
        f"/api/methods/{method['id']}", json={"code": new}, headers=admin.headers
    )
    assert fixed.status_code == 200, fixed.text
    body = fixed.json()
    assert body["code"] == new
    assert body["former_codes"] == [old]
    # 제목이 번호 그대로였으면 제목도 따라간다 — 안 그러면 옛 번호가 제목으로 보인다.
    assert body["title"] == new

    listed = client.get("/api/methods", params={"q": old}, headers=admin.headers).json()
    assert [one["id"] for one in listed["items"]] == [method["id"]], "옛 번호로 못 찾음"

    resolved = client.post(
        "/api/resolve", json={"kind": "method", "text": old}, headers=admin.headers
    ).json()
    assert resolved["match"] == "exact" and resolved["id"] == method["id"]

    # 반입이 쓰는 색인 — 옛 번호로 같은 규격을 또 만들지 않는다.
    db.expire_all()
    assert str(code_index(db)[method_key(old)].id) == method["id"]


def test_번호는_시스템_관리자만_고친다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """부서 시험법이라도 번호는 규격의 열쇠다 — 제목은 부서 관리자가 고치되 번호는 아니다."""
    from app.modules.accounts.models import User
    from app.modules.auth import security
    from app.modules.workspaces.models import WorkspaceMember

    method = _method(client, admin, workspace_slug=admin.workspace)
    email = f"method-manager-{uuid.uuid4().hex[:6]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-manager"),
        display_name="부서 관리자",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
    db.commit()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "pw-manager"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    titled = client.patch(
        f"/api/methods/{method['id']}", json={"title": "사내 굽힘 시험법"}, headers=headers
    )
    assert titled.status_code == 200, titled.text
    refused = client.patch(
        f"/api/methods/{method['id']}", json={"code": "사내-001"}, headers=headers
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-METHODS-0010"


def test_다른_규격의_번호나_옛_번호와_겹치면_거절한다(
    client: TestClient, admin: Signed
) -> None:
    first = _method(client, admin)
    second = _method(client, admin)

    same = client.patch(
        f"/api/methods/{second['id']}", json={"code": first["code"]}, headers=admin.headers
    )
    assert same.status_code == 409, same.text
    assert same.json()["error"]["code"] == "TSC-METHODS-0003"

    old = first["code"]
    moved = client.patch(
        f"/api/methods/{first['id']}",
        json={"code": f"{old} REV"},
        headers=admin.headers,
    )
    assert moved.status_code == 200, moved.text
    # 옛 번호를 다른 규격이 가져가면 반입 · 검토함이 그 번호를 어느 규격으로 볼지 못 가린다.
    taken = client.patch(
        f"/api/methods/{second['id']}", json={"code": old}, headers=admin.headers
    )
    assert taken.status_code == 409, taken.text
    assert taken.json()["error"]["code"] == "TSC-METHODS-0011"


def test_검토함의_규격_물음이_새_번호로_옮겨_간다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.review.models import ReviewProposal

    method = _method(client, admin)
    old = method["code"]
    db.add(
        ReviewProposal(
            queue="method_test_items",
            subject_key=method_key(old),
            subject_id=uuid.UUID(method["id"]),
            subject_label=old,
            candidates=[],
            status="open",
        )
    )
    db.commit()

    new = f"{old}-1"
    fixed = client.patch(
        f"/api/methods/{method['id']}", json={"code": new}, headers=admin.headers
    )
    assert fixed.status_code == 200, fixed.text

    db.expire_all()
    row = db.scalar(
        select(ReviewProposal).where(
            ReviewProposal.queue == "method_test_items",
            ReviewProposal.subject_id == uuid.UUID(method["id"]),
        )
    )
    assert row is not None
    assert row.subject_key == method_key(new)
    assert row.subject_label == new
