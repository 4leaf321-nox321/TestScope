"""지식 그래프 — **큰 데이터를 통째로 안 준다.**

여기서 지키는 것 — 구조는 종류·선 종류와 실제 수 · 찾기는 종류를 가리지 않는다 · 이웃은 상한
안에서 오고 잘리면 잘렸다고 말한다(degree > 화면 수) · 보이는 장비만 · 노드 상세에 관계 목록 ·
없는 노드는 404.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _term(client: TestClient, admin: Signed, axis: str, value: str) -> str:
    made = client.post(
        f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_구조와_찾기와_이웃이_한_사슬로_이어진다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    item = _term(client, admin, "test_item", f"인장-{tag}")
    prop = _term(client, admin, "property", f"인장강도-{tag}")
    linked = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop},
        headers=admin.headers,
    )
    assert linked.status_code == 201, linked.text
    series = client.post(
        "/api/equipment-series", json={"name": f"계열-{tag}"}, headers=admin.headers
    ).json()
    added = client.post(
        f"/api/equipment-series/{series['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text
    method = client.post(
        "/api/methods",
        json={"code": f"ISO {tag}", "title": "인장 규격", "test_item_term_id": item},
        headers=admin.headers,
    ).json()

    overview = client.get("/api/graph/overview", headers=admin.headers)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    types = {one["slug"]: one for one in body["nodes"]}
    assert types["test_item"]["count"] >= 1 and types["series"]["count"] >= 1
    edges = {(e["relation"], e["src_type"], e["dst_type"]): e for e in body["edges"]}
    assert edges[("measures", "test_item", "property")]["count"] >= 1
    assert edges[("performs", "series", "test_item")]["count"] >= 1
    assert edges[("belongs_to", "method", "test_item")]["count"] >= 1
    # 정의만 있고 비어 있을 수 있는 선도 목록에 있다(0 이면 점선).
    assert ("run_by", "reliability_test", "workspace") in edges

    hits = client.get("/api/graph/search", params={"q": f"인장-{tag}"}, headers=admin.headers)
    assert hits.status_code == 200
    found = {one["type_slug"]: one for one in hits.json()}
    assert found["test_item"]["id"] == f"test_item:{item}"

    near = client.get(
        "/api/graph/neighborhood",
        params={"focus": f"test_item:{item}", "depth": 1},
        headers=admin.headers,
    )
    assert near.status_code == 200, near.text
    graph = near.json()
    ids = {one["id"] for one in graph["nodes"]}
    assert {
        f"test_item:{item}",
        f"property:{prop}",
        f"series:{series['id']}",
        f"method:{method['id']}",
    } <= ids
    focus = next(one for one in graph["nodes"] if one["id"] == f"test_item:{item}")
    assert focus["degree"] == 3 and focus["truncated"] is False
    assert focus["detail_path"] == f"/catalog/test-items/{item}"
    relations = {e["relation"] for e in graph["edges"]}
    assert {"measures", "performs", "belongs_to"} <= relations

    # fanout 1 — 셋 중 하나만 오고 잘렸다고 말한다.
    cut = client.get(
        "/api/graph/neighborhood",
        params={"focus": f"test_item:{item}", "depth": 1, "fanout": 1},
        headers=admin.headers,
    ).json()
    assert len(cut["nodes"]) == 2 and cut["truncated"] is True
    assert next(one for one in cut["nodes"] if one["id"] == f"test_item:{item}")["truncated"]

    # 이웃 종류 거르기 — 계열만.
    only = client.get(
        "/api/graph/neighborhood",
        params={"focus": f"test_item:{item}", "types": "series"},
        headers=admin.headers,
    ).json()
    assert {one["type_slug"] for one in only["nodes"]} == {"test_item", "series"}

    detail = client.get(
        "/api/graph/node", params={"id": f"test_item:{item}"}, headers=admin.headers
    )
    assert detail.status_code == 200, detail.text
    labels = {(one["label"], one["outgoing"]) for one in detail.json()["related"]}
    assert ("측정 물성", True) in labels and ("수행 가능 계열", False) in labels
    assert detail.json()["related_total"] == 3

    sub = client.get(
        "/api/graph/subgraph",
        params={"types": "test_item,series", "q": tag},
        headers=admin.headers,
    )
    assert sub.status_code == 200, sub.text
    assert sub.json()["total"] >= 2
    assert any(e["relation"] == "performs" for e in sub.json()["edges"])

    missing = client.get(
        "/api/graph/neighborhood",
        params={"focus": f"series:{uuid.uuid4()}"},
        headers=admin.headers,
    )
    assert missing.status_code == 404
    assert (
        client.get(
            "/api/graph/node", params={"id": "nonsense"}, headers=admin.headers
        ).status_code
        == 404
    )


def test_보이는_장비만_그래프에_든다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """부서가 가린 장비는 남의 그림에 없다 — 검색·이웃·목록·구조 수 어디에도."""
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{tag}",
            "name": f"챔버-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    node = f"equipment:{made.json()['id']}"
    hits = client.get("/api/graph/search", params={"q": f"챔버-{tag}"}, headers=admin.headers)
    assert any(one["id"] == node for one in hits.json())
    near = client.get("/api/graph/neighborhood", params={"focus": node}, headers=admin.headers)
    assert {e["relation"] for e in near.json()["edges"]} >= {"owned_by", "located_at"}
    browse = client.get(
        "/api/graph/browse", params={"type": "equipment", "q": tag}, headers=admin.headers
    ).json()
    assert browse["total"] == 1 and browse["items"][0]["key"] == f"EQ-{tag}"

    # 부서를 가리고 남의 부서 사람으로 본다 — 어디에도 없다.
    workspace.restricted = True
    other = Workspace(slug=f"other-{uuid.uuid4().hex[:8]}", name="다른팀")
    db.add(other)
    db.flush()
    email = f"member-{uuid.uuid4().hex[:8]}@testscope.local"
    member = User(
        email=email,
        password_hash=security.hash_password("member-password"),
        display_name="멤버",
        status="active",
        home_workspace_id=other.id,
    )
    db.add(member)
    db.flush()
    db.add(WorkspaceMember(workspace_id=other.id, user_id=member.id, role="member"))
    db.commit()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "member-password"}
    ).json()["access_token"]
    outsider = {"Authorization": f"Bearer {token}"}

    hits = client.get("/api/graph/search", params={"q": f"챔버-{tag}"}, headers=outsider)
    assert all(one["id"] != node for one in hits.json())
    assert (
        client.get(
            "/api/graph/neighborhood", params={"focus": node}, headers=outsider
        ).status_code
        == 404
    )
    assert (
        client.get("/api/graph/node", params={"id": node}, headers=outsider).status_code == 404
    )
    browse = client.get(
        "/api/graph/browse", params={"type": "equipment", "q": tag}, headers=outsider
    ).json()
    assert browse["total"] == 0
    mine = client.get("/api/graph/overview", headers=admin.headers).json()
    theirs = client.get("/api/graph/overview", headers=outsider).json()
    counts = [
        next(one["count"] for one in body["nodes"] if one["slug"] == "equipment")
        for body in (theirs, mine)
    ]
    assert counts[0] < counts[1]
