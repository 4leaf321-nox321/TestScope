"""카탈로그 기종 등록 요청 — **못 고르는 쪽에 말할 자리.**

장비를 등록할 때 카탈로그에 그 기종이 없으면 비워 두게 되어 있다. 그 안내는 맞지만(비슷한
기종을 고르면 그 장비의 하중·온도가 남의 것이 된다), 비워 둔 다음에 **왜 비었는지가 아무
데도 안 남았다.**

여기서 지키는 것:

1. 장비를 고칠 수 있는 사람이면 요청을 남긴다 — 카탈로그 정본은 안 건드린다.
2. 같은 것을 두 번 내도 **거절하지 않는다** — 등록 창을 다시 저장하는 일이 흔하다.
3. 같은 기종을 여러 장비가 요청하면 **한 줄로 모인다** — 관리자는 다섯 번이 아니라 한 번.
4. 정하는 것은 **시스템 관리자만.**
5. 정하면 **요청한 장비들이 실제로 이어진다** — 여기까지 안 하면 관리자가 장비를 하나씩
   열어 다시 골라야 하고, 그 일이 밀리면 요청은 정해졌는데 장비는 미연결로 남는다.
6. 이으면 개체가 적어 둔 제조사·모델명·분류는 서버가 비운다 — 같은 사실이 두 곳에 남으면
   갈린 뒤에 어느 쪽이 맞는지 알 방법이 없다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, category_id, site_id


def _equipment(client: TestClient, admin: Signed, tag: str, **extra: Any) -> dict[str, Any]:
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{tag}-{uuid.uuid4().hex[:4]}",
            "name": f"만능기-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
            "maker_text": "Instron",
            "model_text": f"68FM-300-{tag}",
            **extra,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    out: dict[str, Any] = made.json()
    return out


def _propose(client: TestClient, admin: Signed, equipment_id: str, **body: Any) -> Any:
    return client.post(
        f"/api/equipment/{equipment_id}/model-proposals", json=body, headers=admin.headers
    )


def _groups(client: TestClient, admin: Signed) -> list[dict[str, Any]]:
    got = client.get("/api/equipment-models/proposals", headers=admin.headers)
    assert got.status_code == 200, got.text
    rows: list[dict[str, Any]] = got.json()
    return rows


def test_요청을_남기고_같은_것끼리_모인다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    one = _equipment(client, admin, tag)
    two = _equipment(client, admin, tag)

    made = _propose(
        client,
        admin,
        one["id"],
        maker_text="Instron",
        model_text=f"68FM-300-{tag}",
        note="6800 시리즈는 있는데 이 모델만 없음",
    )
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "open"
    assert made.json()["text"] == f"Instron 68FM-300-{tag}"

    # **같은 요청을 두 번 내도 거절하지 않는다** — 등록 창을 다시 저장하면 그렇게 된다.
    again = _propose(
        client, admin, one["id"], maker_text="Instron", model_text=f"68FM-300-{tag}"
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] == made.json()["id"]

    # 표기가 갈려도 한 줄로 모인다 — 띄어쓰기·대소문자를 지운 비교키로 센다.
    other = _propose(
        client, admin, two["id"], maker_text="instron", model_text=f"68fm-300-{tag}"
    )
    assert other.status_code == 201, other.text

    mine = [g for g in _groups(client, admin) if tag.lower() in g["normalized"]]
    assert len(mine) == 1, mine
    assert mine[0]["count"] == 2

    # 그 장비 화면에서도 보인다 — **왜 기종이 비었는지가 그 줄에 있어야 한다.**
    listed = client.get(f"/api/equipment/{one['id']}/model-proposals", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    assert [row["note"] for row in listed.json()] == ["6800 시리즈는 있는데 이 모델만 없음"]


def test_정하면_요청한_장비들이_한꺼번에_이어진다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    one = _equipment(client, admin, tag)
    two = _equipment(client, admin, tag)
    for row in (one, two):
        assert (
            _propose(
                client, admin, row["id"], maker_text="Instron", model_text=f"68FM-{tag}"
            ).status_code
            == 201
        )

    series = client.post(
        "/api/equipment-series",
        json={"name": f"6800 시리즈-{tag}", "category_term_id": category_id(client, admin)},
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text

    mine = next(g for g in _groups(client, admin) if tag.lower() in g["normalized"])
    decided = client.post(
        "/api/equipment-models/proposals/decide",
        json={
            "normalized": mine["normalized"],
            "series_id": series.json()["id"],
            "name": f"68FM-{tag}",
        },
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "created"
    # **두 대가 함께 이어진다** — 하나씩 열어 다시 고르는 일이 이 기능이 없앤 것이다.
    assert body["decided"] == 2 and body["linked"] == 2 and body["failed"] == []

    for row in (one, two):
        again = client.get(f"/api/equipment/{row['id']}", headers=admin.headers).json()
        assert again["model_id"] == body["model_id"]
        assert again["model_name"] == f"68FM-{tag}"
        # 이으면 **카탈로그가 진실이 된다** — 개체가 적어 둔 제조사·모델명은 서버가 비우고,
        # 화면이 읽는 칸은 그때부터 계열의 값에서 온다.
        assert again["catalog_linked"] is True

    # 정한 요청은 목록에서 빠진다 — 남아 있으면 관리자가 같은 것을 또 본다.
    assert [g for g in _groups(client, admin) if tag.lower() in g["normalized"]] == []


def test_아니라고도_정한다(client: TestClient, admin: Signed) -> None:
    """자작 장비처럼 **카탈로그에 올릴 것이 아닌** 경우가 실제로 있다."""
    tag = uuid.uuid4().hex[:6]
    row = _equipment(client, admin, tag)
    assert (
        _propose(client, admin, row["id"], model_text=f"사내 자작 치구-{tag}").status_code
        == 201
    )

    mine = next(g for g in _groups(client, admin) if tag.lower() in g["normalized"])
    decided = client.post(
        "/api/equipment-models/proposals/decide",
        json={"normalized": mine["normalized"]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "rejected"
    assert decided.json()["linked"] == 0
    # 장비는 그대로 미연결 — 아니라고 한 것이 장비를 건드리지는 않는다.
    assert (
        client.get(f"/api/equipment/{row['id']}", headers=admin.headers).json()["model_id"]
        is None
    )


def test_정하는_것은_시스템_관리자만(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """카탈로그 정본은 아무나 못 고친다 — 기종을 고르면 그 계열의 시험 항목이 복사되고
    조건 판정이 그 사양을 쓴다. 아무나 세운 기종은 **잘못된 답의 근거**가 된다."""
    from app.modules.accounts.models import User
    from app.modules.auth import security
    from app.modules.workspaces.models import WorkspaceMember

    tag = uuid.uuid4().hex[:6]
    row = _equipment(client, admin, tag)
    assert _propose(client, admin, row["id"], model_text=f"68FM-{tag}").status_code == 201

    email = f"member-{tag}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-member"),
        display_name="구성원",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "pw-member"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    mine = next(g for g in _groups(client, admin) if tag.lower() in g["normalized"])
    refused = client.post(
        "/api/equipment-models/proposals/decide",
        json={"normalized": mine["normalized"]},
        headers=headers,
    )
    assert refused.status_code == 403, refused.text
    # **왜 막혔는지를 말한다** — 「권한 없음」 만 오면 사람은 토큰을 다시 만들러 간다.
    assert "시스템 관리자" in refused.json()["error"]["message"]
