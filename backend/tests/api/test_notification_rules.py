"""알림이 **실제로 울리나** — 표와 화면은 있었는데 만드는 곳이 없었다.

메일이 없는 환경이라 앱 안 알림이 유일한 전달 경로다. 아무 일에도 안 울리는 종은 곧
아무도 안 본다. 규칙은 `notifications/rules.py` 한 곳이고, 여기서는 네 규칙이 도는지와
**같은 일로 두 번 안 울리는지**를 본다.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.notifications import rules
from app.modules.notifications.models import Notification
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _mine(client: TestClient, who: Signed) -> list[dict[str, Any]]:
    response = client.get("/api/notifications", headers=who.headers)
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


def _manager(client: TestClient, db: Session, workspace: Workspace) -> tuple[User, Signed]:
    """그 부서의 관리자 한 명 더 — 알림을 **받는** 쪽."""
    email = f"manager-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("manager-password"),
        display_name="부서장",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
    db.commit()
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "manager-password"}
    )
    assert login.status_code == 200, login.text
    return user, Signed(
        email=email, token=login.json()["access_token"], workspace=workspace.slug
    )


def _equipment(client: TestClient, admin: Signed, **extra: Any) -> dict[str, Any]:
    response = client.post(
        "/api/equipment",
        json={
            "asset_no": f"NT-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "category_term_id": category_id(client, admin),
            "location": "3동 201호",
            "name": "충격시험기",
            "workspace_slug": admin.workspace,
            **extra,
        },
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    row: dict[str, Any] = response.json()
    return row


def test_가입_신청은_관리자에게_승인은_신청자에게_간다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    email = f"new-{uuid.uuid4().hex[:8]}@testscope.local"
    signed_up = client.post(
        "/api/accounts/signup",
        json={
            "email": email,
            "password": "new-user-password",
            "display_name": "신입",
            "workspace_slug": admin.workspace,
        },
    )
    assert signed_up.status_code == 201, signed_up.text
    new_id = signed_up.json()["id"]

    pending = [one for one in _mine(client, admin) if one["kind"] == "account.pending"]
    assert any(one["title"] == "가입 신청: 신입" for one in pending)
    assert all(one["link"] == "/admin/accounts?status=pending" for one in pending)

    approved = client.post(
        f"/api/accounts/{new_id}/approve",
        json={"workspace_slug": admin.workspace, "role": "member"},
        headers=admin.headers,
    )
    assert approved.status_code == 200, approved.text
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "new-user-password"}
    )
    assert login.status_code == 200, login.text
    me = Signed(email=email, token=login.json()["access_token"], workspace=admin.workspace)
    kinds = [one["kind"] for one in _mine(client, me)]
    assert kinds == ["account.approved"], "승인된 사람이 처음 보는 것이 「승인됐다」 여야 한다"


def test_장비_상태_변경은_부서_관리자에게_가되_바꾼_사람에게는_안_간다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    _, signed = _manager(client, db, workspace)
    equipment = _equipment(client, admin)

    changed = client.patch(
        f"/api/equipment/{equipment['id']}", json={"status": "repair"}, headers=admin.headers
    )
    assert changed.status_code == 200, changed.text

    got = [one for one in _mine(client, signed) if one["kind"] == "equipment.status_changed"]
    assert len(got) == 1
    assert got[0]["title"].endswith("가동 → 고장")
    assert got[0]["link"] == f"/equipment/{equipment['id']}"
    # 바꾼 사람 본인에게는 안 간다 — 자기가 한 일을 자기에게 알리면 알림은 소음이 된다.
    assert not any(
        one["kind"] == "equipment.status_changed" and one["link"] == got[0]["link"]
        for one in _mine(client, admin)
    )


def test_교정_만료는_훑기가_만들고_같은_만료일에는_한_번만(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    manager, signed = _manager(client, db, workspace)
    soon = _equipment(client, admin, calibration_required=True, calibration_interval_months=12)
    late = _equipment(client, admin, calibration_required=True, calibration_interval_months=12)
    far = _equipment(client, admin, calibration_required=True, calibration_interval_months=12)
    today = date.today()
    for row, due in (
        (soon, today + timedelta(days=30)),
        (late, today - timedelta(days=5)),
        (far, today + timedelta(days=200)),
    ):
        added = client.post(
            f"/api/equipment/{row['id']}/calibrations",
            json={
                "calibrated_on": (today - timedelta(days=300)).isoformat(),
                "next_due_on": due.isoformat(),
            },
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text

    assert rules.sweep_calibration(db, manager, today=today) == 2
    db.commit()
    # 두 번째 훑기는 아무것도 안 만든다 — 같은 장비의 같은 만료일이다.
    assert rules.sweep_calibration(db, manager, today=today) == 0

    titles = {
        one["link"]: one["title"]
        for one in _mine(client, signed)
        if one["kind"] == "calibration.due"
    }
    assert titles[f"/equipment/{soon['id']}"].endswith("교정 30일 남음")
    assert titles[f"/equipment/{late['id']}"].endswith("교정 기한 5일 지남")
    assert f"/equipment/{far['id']}" not in titles, "200일 뒤 것은 아직 알릴 일이 아니다"

    # 다시 교정을 받아 만료일이 바뀌면 새 알림이 선다 — 옛 만료일의 알림과 다른 일이다.
    renewed = client.post(
        f"/api/equipment/{late['id']}/calibrations",
        json={
            "calibrated_on": today.isoformat(),
            "next_due_on": (today + timedelta(days=10)).isoformat(),
        },
        headers=admin.headers,
    )
    assert renewed.status_code == 201, renewed.text
    assert rules.sweep_calibration(db, manager, today=today) == 1
    db.commit()
    keys = set(
        db.scalars(
            select(Notification.dedupe_key).where(
                Notification.user_id == manager.id, Notification.kind == "calibration.due"
            )
        )
    )
    assert len(keys) == 3
