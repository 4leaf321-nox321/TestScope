"""신뢰성 시험 — 부서가 등록하는, 제품 개발·검증을 위한 시험 절차.

「시험 항목」(장비가 할 수 있는 측정, 전사 공용)과 다른 층이다. 여기서 지키는 것 — 읽기는
누구나·쓰기는 그 부서의 관리자 · 같은 부서에 같은 이름은 하나 · 시험 항목 축의 값만 잇는다 ·
지우면 사라지되 감사에 남는다.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.audit.models import AuditEntry
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _term(client: TestClient, admin: Signed, axis: str, value: str) -> str:
    made = client.post(
        f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _signed_in(client: TestClient, db: Session, workspace: Workspace, role: str) -> Signed:
    email = f"{role}-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-" + role),
        display_name=role,
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw-" + role})
    return Signed(email=email, token=token.json()["access_token"], workspace=workspace.slug)


def test_그_부서의_관리자만_등록하고_누구나_본다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    lab = Workspace(slug=f"lab-{tag}", name="신뢰성팀")
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    member = _signed_in(client, db, lab, "member")

    body = {"workspace_slug": lab.slug, "name": f"고온고습-{tag}", "purpose": "85/85 1000h"}
    assert (
        client.post("/api/reliability-tests", json=body, headers=member.headers).status_code
        == 403
    )
    made = client.post("/api/reliability-tests", json=body, headers=manager.headers)
    assert made.status_code == 201, made.text
    assert made.json()["can_edit"] is True

    # **다른 부서 사람도 본다** — 이 시스템의 물음은 부서를 가로지른다. 고치지는 못한다.
    seen = client.get(
        "/api/reliability-tests", params={"workspace": lab.slug}, headers=admin.headers
    )
    assert [one["name"] for one in seen.json()] == [f"고온고습-{tag}"]
    as_member = client.get(
        f"/api/reliability-tests/{made.json()['id']}", headers=member.headers
    )
    assert as_member.status_code == 200 and as_member.json()["can_edit"] is False

    # 같은 부서에 같은 이름은 하나 — 대소문자만 달라도.
    clash = client.post(
        "/api/reliability-tests",
        json={**body, "name": f"고온고습-{tag.upper()}"},
        headers=manager.headers,
    )
    assert clash.status_code == 409


def test_시험_항목을_잇고_그_부서의_장비_수를_센다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    shock = _term(client, admin, "test_item", f"열충격-{tag}")
    site = site_id(client, admin)

    # 시험 항목 축이 아닌 값은 거절 — 「인장」 자리에 「3동」 이 그려지지 않게.
    wrong = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"TS-{tag}",
            "test_item_term_ids": [site],
        },
        headers=admin.headers,
    )
    assert wrong.status_code == 400, wrong.text

    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"TS-{tag}",
            "test_item_term_ids": [shock],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    assert made.json()["test_items"][0]["equipment_count"] == 0

    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"CH-{tag}",
            "name": "열충격 챔버",
            "workspace_slug": admin.workspace,
            "site_term_id": site,
            "location": "2동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    ).json()
    client.post(
        "/api/equipment-test-items",
        json={"equipment_id": equipment["id"], "test_item_term_id": shock},
        headers=admin.headers,
    )
    again = client.get(f"/api/reliability-tests/{made.json()['id']}", headers=admin.headers)
    assert again.json()["test_items"][0]["equipment_count"] == 1

    # 통째로 바꾼다 — 비우면 빈다. 이름만 고칠 때는 안 건드린다.
    client.patch(
        f"/api/reliability-tests/{made.json()['id']}",
        json={"name": f"TS2-{tag}"},
        headers=admin.headers,
    )
    kept = client.get(f"/api/reliability-tests/{made.json()['id']}", headers=admin.headers)
    assert len(kept.json()["test_items"]) == 1
    client.patch(
        f"/api/reliability-tests/{made.json()['id']}",
        json={"test_item_term_ids": []},
        headers=admin.headers,
    )
    emptied = client.get(f"/api/reliability-tests/{made.json()['id']}", headers=admin.headers)
    assert emptied.json()["test_items"] == []


def test_지우면_목록에서_빠지고_감사에_남는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": admin.workspace, "name": f"낙하-{tag}"},
        headers=admin.headers,
    ).json()
    gone = client.delete(f"/api/reliability-tests/{made['id']}", headers=admin.headers)
    assert gone.status_code == 204
    assert (
        client.get(f"/api/reliability-tests/{made['id']}", headers=admin.headers).status_code
        == 404
    )
    entry = db.scalar(
        select(AuditEntry).where(
            AuditEntry.action == "reliability_test.deleted",
            AuditEntry.target_id == uuid.UUID(made["id"]),
        )
    )
    assert entry is not None and f"낙하-{tag}" in entry.target_label
    # 지운 이름은 다시 쓸 수 있다 — 부분 유일 인덱스.
    again = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": admin.workspace, "name": f"낙하-{tag}"},
        headers=admin.headers,
    )
    assert again.status_code == 201
